import os
import json
import pika
import traceback
from utils.constant import AUDIO_ANALYSIS_QUEUE, LLM_EVALUATION_QUEUE, AUDIO_ANALYSIS_DELAY_QUEUE
from config.db import task_collection, question_result_collection
from bson import ObjectId
from ai_modules.audio_analysis import audio_analysis_pipeline
from datetime import datetime
from pymongo import ReturnDocument
from utils.rabbitmq import connect_rabbitmq, initialize_queues
from utils.logger_config import setup_logging
import logging


setup_logging("logger/audio_worker.log")
logger = logging.getLogger(__name__)

# --- Setup RabbitMQ Connection ---
channel, connection = connect_rabbitmq()

# Initializing the queues and exchange

initialize_queues(channel=channel)

channel.confirm_delivery()


def create_and_push_llm_evaluation_task_to_queue(question_result_id: str, candidate_id: str) -> ObjectId:
    """Create a new audio analysis task document and push it to the audio analysis queue."""
    try:
        doc = {
            "userId": candidate_id,
            "type": "llm_evaluation",
            "status": "pending",
            "payload": {
                "questionResultId": question_result_id,
            },
        }
        result = task_collection.insert_one(doc)
        if not result.acknowledged or not result.inserted_id:
            logger.warning("Task creation failed")
            return False
        logger.info("Task created successfully with ID: %s", result.inserted_id)
        body = str(result.inserted_id).encode()
        channel.basic_publish(
            exchange='',
            routing_key=LLM_EVALUATION_QUEUE,
            body=body,
            properties=pika.BasicProperties(
                delivery_mode=pika.DeliveryMode.Persistent,
            ),
            mandatory=True  # raise on unroutable
        )
        logger.info("Enqueued llm evaluation task %s for question result %s", result.inserted_id, question_result_id)
        return True
    except Exception as e:
        logger.exception("Error creating and pushing llm evaluation task")
        return False


def callback(ch, method, properties, body):
    task_id = body.decode()
    logger.info("Task received | task_id=%s", task_id)
    
    if not ObjectId.is_valid(task_id):
        ch.basic_ack(delivery_tag=method.delivery_tag)
        return
    
    try:
        # Fetch task
        task = task_collection.find_one_and_update({"_id": ObjectId(task_id), "status": "pending"}, {"$set": {"status": "processing"}})
        if not task:
            actual_task = task_collection.find_one({"_id": ObjectId(task_id)})
            if not actual_task:
                logger.warning("Task not found | task_id=%s", task_id)
            else:
                logger.warning("Task skip: Current status is %s", actual_task.get('status'))
            ch.basic_ack(delivery_tag=method.delivery_tag)
            return

        logger.debug(
            "Task fetched | task_id=%s | user_id=%s",
            task_id,
            task.get("userId")
        )

        candidate_id=task['userId']
    
        # fetching the question result id for fetching the question result document
        question_result_id = task["payload"]["questionResultId"]
        
        result = audio_analysis_pipeline(question_result_id)
        if not result:
            logger.info("Acknowledge the task because question does not exist")
            ch.basic_ack(delivery_tag=method.delivery_tag)
        
        logger.info("Task %s audio analysis completed successfully now pushing to LLM evaluation queue", task_id)
        
        # Now push to the llm queue
        result = question_result_collection.find_one_and_update(
            {
                "_id": ObjectId(question_result_id),
                "status": "PROCESSING",
                "stages.audioAnalyzed": True,
                "stages.videoAnalyzed": True,
                "llmEnqueued": False,
            },
            {
                "$set": {
                    "llmEnqueued": True,
                    "llmStartedAt": datetime.utcnow(),
                }
            },
            return_document=ReturnDocument.AFTER
        )
        
        if result:
            # create a task and push it in the llm queue
            create_and_push_llm_evaluation_task_to_queue(question_result_id, candidate_id)
        else:
            logger.info("Skipping LLM enqueue - conditions not met")
        
        # --- Mark Task as Completed ---
        task_collection.update_one(
            {"_id": ObjectId(task_id)},
            {"$set": {"status": "completed", "error": None}},
        )
        logger.info("Task completed | task_id=%s", task_id)
        # Acknowledge successful message
        ch.basic_ack(delivery_tag=method.delivery_tag)
    except Exception as e:
        logger.exception("Task crashed | task_id=%s", task_id)
        # Mark task as failed and store error message
        updated_task = task_collection.find_one_and_update(
            {"_id": ObjectId(task_id)},
            {
                "$set": {"status": "failed", "error": str(e)},
                "$inc": {"retryCount": 1}
            },
            return_document=ReturnDocument.AFTER  # This returns the document AFTER the update
        )
        retry_count = updated_task['retryCount']
        if retry_count >=3:
            logger.error("Max retries exceeded. Moving to DLQ | task_id=%s", task_id)
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
        else:
            logger.info("Moving to Waiting Room (10s delay) | retry=%s", retry_count)
            # Manually publish to Delay Queue
            try:
                ch.basic_publish(
                    exchange='',
                    routing_key=AUDIO_ANALYSIS_DELAY_QUEUE,
                    body=body,
                    properties=pika.BasicProperties(delivery_mode=pika.DeliveryMode.Persistent)
                )
                ch.basic_ack(delivery_tag=method.delivery_tag)
            except Exception as publish_error:
                logger.error("Failed to move to delay queue: %s", publish_error)
                # If we can't publish to delay, requeue=True is our safety net
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)



# --- Start Consuming Messages ---
channel.basic_qos(prefetch_count=1)  # Fair dispatch
channel.basic_consume(
    queue=AUDIO_ANALYSIS_QUEUE,
    on_message_callback=callback,
    auto_ack=False  # Manual ack ensures reliability
)

logger.info("Worker started and waiting for audio analysis jobs...")
try:
    channel.start_consuming()
except KeyboardInterrupt:
    logger.info("Worker stopped manually")
    channel.stop_consuming()
    connection.close()