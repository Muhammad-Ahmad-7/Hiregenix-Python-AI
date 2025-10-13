import os
import json
import pika
import traceback
from utils.constant import JOB_DESCRIPTION_EMBEDDINGS_QUEUE
from config.db import task_collection
from bson import ObjectId
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from ai_modules.job_recommendation import run_recommendation_pipeline

load_dotenv()

RABBITMQ_URL = os.getenv("RABBITMQ_URL")

# --- Setup RabbitMQ Connection ---
params = pika.ConnectionParameters(host=RABBITMQ_URL)
connection = pika.BlockingConnection(params)
channel = connection.channel()
channel.queue_declare(queue=JOB_DESCRIPTION_EMBEDDINGS_QUEUE, durable=True)

# --- Main Callback ---
def callback(ch, method, properties, body):
    task_id = body.decode()
    print(f"📥 Received Task {task_id}")

    try:
        # Fetch task
        task = task_collection.find_one({"_id": ObjectId(task_id)})
        if not task:
            print("❌ Task not found in DB")
            ch.basic_ack(delivery_tag=method.delivery_tag)
            return

        print(f" 🔍 Fetched Task {task_id} from DB: {task}")
        task_collection.update_one(
            {"_id": ObjectId(task_id)}, {"$set": {"status": "processing"}}
        )
        print(f"⏳ Task {task_id} status updated to processing")
        
        run_recommendation_pipeline(candidate_id=task["payload"]["candidateId"])
        
        # --- Mark Task as Completed ---
        task_collection.update_one(
            {"_id": ObjectId(task_id)},
            {"$set": {"status": "completed", "error": None}},
        )
        print(f"✅ Task {task_id} completed successfully")

        # Acknowledge successful message
        ch.basic_ack(delivery_tag=method.delivery_tag)

    except Exception as e:
        print(f"❌ Error processing task {task_id}: {e}")
        traceback.print_exc()

        # Mark task as failed and store error message
        task_collection.update_one(
            {"_id": ObjectId(task_id)},
            {"$set": {"status": "failed", "error": str(e)}},
        )

        # Retry logic: requeue message instead of losing it
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
        print(f"🔁 Task {task_id} requeued for retry")

# --- Start Consumer (Manual Ack Mode) ---
channel.basic_consume(
    queue=JOB_DESCRIPTION_EMBEDDINGS_QUEUE,
    on_message_callback=callback,
    auto_ack=False  # Manual ack ensures reliability
)

print("🚀 Worker started and waiting for job recommendation jobs...")
try:
    channel.start_consuming()
except KeyboardInterrupt:
    print("👋 Worker stopped manually")
    channel.stop_consuming()
    connection.close()
