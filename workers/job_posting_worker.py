import pika
from utils.constant import JOB_DESCRIPTION_EMBEDDINGS_QUEUE, JOB_DESCRIPTION_EMBEDDINGS_DELAY_QUEUE
from config.db import task_collection
from bson import ObjectId
from ai_modules.company import generate_job_post_ai_description
from pymongo import ReturnDocument


from utils.logger_config import setup_logging
import logging
from utils.rabbitmq import connect_rabbitmq, initialize_queues



setup_logging("logger/job_posting_worker.log")
logger = logging.getLogger(__name__)

# --- Setup RabbitMQ Connection ---
channel, connection = connect_rabbitmq()

# Initializing the queues and exchange

initialize_queues(channel=channel)

channel.confirm_delivery()

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

        # job ai description + embedding generator
        
        job_id=task["payload"]["jobId"]
        result = generate_job_post_ai_description(job_id=job_id)
        
        if not result:
            logger.warning("Failed to generate AI description for job %s", job_id)
            raise Exception("Failed to generate AI description")
        
        logger.info(f"AI Description generated for job {job_id}")
        
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
            # update the task status back to pending for retry
            task_collection.update_one(
                {"_id": ObjectId(task_id)},
                {"$set": {"status": "pending", "error": None}},
            )
            # Manually publish to Delay Queue
            try:
                ch.basic_publish(
                    exchange='',
                    routing_key=JOB_DESCRIPTION_EMBEDDINGS_DELAY_QUEUE,
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
    queue=JOB_DESCRIPTION_EMBEDDINGS_QUEUE,
    on_message_callback=callback,
    auto_ack=False  # Manual ack ensures reliability
)

try:
    logger.info("Job description embedding generation Worker started, waiting for messages...")
    channel.start_consuming()
except KeyboardInterrupt:
    logger.info("Worker stopped manually")
    channel.stop_consuming()
    connection.close()
