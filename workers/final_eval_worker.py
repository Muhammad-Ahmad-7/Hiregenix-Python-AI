import os
import json
import pika
import traceback
from utils.constant import FINAL_INTERVIEW_EVAL_QUEUE, REPORT_GENERATION_PDF_QUEUE, FINAL_INTERVIEW_EVAL_DELAY_QUEUE
from config.db import task_collection
from ai_modules.final_eval import final_interview_pipeline
from bson import ObjectId
from utils.rabbitmq import connect_rabbitmq, initialize_queues
from utils.logger_config import setup_logging
import logging
from pymongo import ReturnDocument

setup_logging("logger/final_eval_worker.log")
logger = logging.getLogger(__name__)

# --- Setup RabbitMQ Connection ---
channel, connection = connect_rabbitmq()

# Initializing the queues and exchange

initialize_queues(channel=channel)



channel.confirm_delivery()


def create_and_push_report_generation_pdf_task_to_queue(report_id: str, candidate_id: str) -> ObjectId:
    """Create a new audio analysis task document and push it to the audio analysis queue."""
    try:
        doc = {
            "userId": candidate_id,
            "type": "report_generation_pdf",
            "status": "pending",
            "payload": {
                "interview_id": report_id,
            },
        }
        result = task_collection.insert_one(doc)
        if not result.acknowledged or not result.inserted_id:
            logger.warning("Task creation failed")
            return False
        logger.info("Task created successfully with ID: %s", result.inserted_id)
        body = str(result.inserted_id).encode()
        delivered = channel.basic_publish(
            exchange='',
            routing_key=REPORT_GENERATION_PDF_QUEUE,
            body=body,
            properties=pika.BasicProperties(
                delivery_mode=pika.DeliveryMode.Persistent,
            ),
            mandatory=True  # raise on unroutable
        )
        logger.info("Enqueued pdf report generation task %s for report id %s", result.inserted_id, report_id)
        return True
    except pika.exceptions.AMQPChannelError as e:
        logger.error("Error: %s", e)
        # Handle channel errors, e.g., if the message was nack-ed or unroutable
    except Exception as e:
        logger.error("Error creating and pushing llm evaluation task: {%s}",e)
        return False

# --- Main Callback ---
def callback(ch, method, properties, body):
    task_id = body.decode()
    logger.info("Task received | task_id=%s", task_id)
    
    if not ObjectId.is_valid(task_id):
        logger.info("Invalid task id")
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
        
        interview_id = task["payload"]["interview_id"]
        
        result = final_interview_pipeline(interview_id=interview_id)
        
        if not result:
            logger.info("Acknowledge the task because interview does not exist")
            ch.basic_ack(delivery_tag=method.delivery_tag)
        
        report_id = result
        
        logger.info("Task %s final interview evaluation completed successfully now pushing to pdf report generation queue", task_id)
        res = create_and_push_report_generation_pdf_task_to_queue(report_id=report_id, candidate_id=candidate_id)
        
        if not res:
            raise Exception("Report generation pdf task not created in DB")
        
        logger.info("New Task %s report generation pdf task created successfully", task_id)
        
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
                    routing_key=FINAL_INTERVIEW_EVAL_DELAY_QUEUE,
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
    queue=FINAL_INTERVIEW_EVAL_QUEUE,
    on_message_callback=callback,
    auto_ack=False  # Manual ack ensures reliability
)

try:
    logger.info("Worker started and waiting for final interview evaluation jobs...")
    channel.start_consuming()
except KeyboardInterrupt:
    print("👋 Worker stopped manually")
    channel.stop_consuming()
    connection.close()