import os
import json
import pika
import traceback

from pymongo import ReturnDocument
from utils.constant import CANDIDATE_PROFILE_EMBEDDINGS_DELAY_QUEUE, CANDIDATE_PROFILE_EMBEDDINGS_QUEUE, JOB_RECOMMENDATION_QUEUE
from ai_modules.candidate import generate_candidate_profile_ai_description
from config.db import candidate_collection, task_collection
from bson import ObjectId
from dotenv import load_dotenv
from utils.logger_config import setup_logging
import logging
from utils.rabbitmq import connect_rabbitmq, initialize_queues



setup_logging("logger/candidate_worker.log")
logger = logging.getLogger(__name__)

# --- Setup RabbitMQ Connection ---
channel, connection = connect_rabbitmq()

# Initializing the queues and exchange

initialize_queues(channel=channel)

channel.confirm_delivery()


def create_recommendation_task(candidate_id: str) -> ObjectId:
    """Create a new recommendation task document and return its _id."""
    doc = {
        "userId": candidate_id,
        "type": "job_recommendation",
        "status": "pending",
        "payload": {
            "candidateId": candidate_id,
        },
    }
    result = task_collection.insert_one(doc)
    logger.info("Created recommendation task for candidate %s with ID: %s", candidate_id, result.inserted_id)
    if not result.acknowledged or not result.inserted_id:
        logger.warning("Recommendation task creation failed for candidate %s", candidate_id)
        return None
    return result.inserted_id


def create_and_push_recommendation_task_to_queue(candidate_id: str) -> bool:
    """Create a new recommendation task document and push it to the recommendation queue."""
    try:
        rec_task_id = create_recommendation_task(candidate_id=candidate_id)
        if not rec_task_id:
            logger.warning("Recommendation task not created in DB for candidate %s", candidate_id)
            return False
        body = str(rec_task_id).encode()
        channel.basic_publish(
            exchange='',
            routing_key=JOB_RECOMMENDATION_QUEUE,
            body=body,
            properties=pika.BasicProperties(
                delivery_mode=pika.DeliveryMode.Persistent,
            ),
            mandatory=True  # raise on unroutable
        )
        logger.info("Enqueued recommendation task %s for candidate %s", rec_task_id, candidate_id)
        return True
    except Exception as e:
        logger.error("Error creating/publishing recommendation task for candidate %s: %s", candidate_id, str(e))
        traceback.print_exc()
        return False

# --- Main Callback ---
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
            logger.info("Acknowledged message for non-pending task | task_id=%s", task_id)
            return

        logger.info(
            "Task fetched | task_id=%s | user_id=%s",
            task_id,
            task.get("userId")
        )
        candidate_id = task["payload"]["candidateId"]
        candidate = candidate_collection.find_one({"_id": ObjectId(candidate_id)})

        if not candidate:
            logger.warning("Candidate not found in DB | candidate_id=%s", candidate_id)
            ch.basic_ack(delivery_tag=method.delivery_tag)
            return

        logger.info("Processing candidate profile embedding for candidate %s", candidate_id)

        skills = candidate.get("skills", [])
        bio = candidate.get("bio", "")

        # --- Generate Description ---
        generate_candidate_profile_ai_description(candidate_id=candidate_id, skills=skills, bio=bio)

        # --- Mark Task as Completed ---
        task_collection.update_one(
            {"_id": ObjectId(task_id)},
            {"$set": {"status": "completed", "error": None}},
        )
        
        logger.info("Task completed | task_id=%s", task_id)
        
        push_queue_res =create_and_push_recommendation_task_to_queue(candidate_id=candidate_id)
        
        if not push_queue_res:
            logger.warning("Failed to enqueue recommendation task for candidate %s", candidate_id)
            raise Exception("Failed to enqueue recommendation task")

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
            # update the task status back to pending for retry
            task_collection.update_one(
                {"_id": ObjectId(task_id)},
                {"$set": {"status": "pending", "error": None}},
            )
            # Manually publish to Delay Queue
            try:
                ch.basic_publish(
                    exchange='',
                    routing_key=CANDIDATE_PROFILE_EMBEDDINGS_DELAY_QUEUE,
                    body=body,
                    properties=pika.BasicProperties(delivery_mode=pika.DeliveryMode.Persistent)
                )
                ch.basic_ack(delivery_tag=method.delivery_tag)
            except Exception as publish_error:
                logger.error("Failed to move to delay queue: %s", publish_error)
                # If we can't publish to delay, requeue=True is our safety net
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

# --- Start Consumer (Manual Ack Mode) ---
channel.basic_qos(prefetch_count=1)
channel.basic_consume(
    queue=CANDIDATE_PROFILE_EMBEDDINGS_QUEUE,
    on_message_callback=callback,
    auto_ack=False  # Manual ack ensures reliability
)

try:
    logger.info("Candidate Worker started. Waiting for messages...")
    channel.start_consuming()
except KeyboardInterrupt:
    logger.info("Candidate Worker stopped manually")
    channel.stop_consuming()
    connection.close()