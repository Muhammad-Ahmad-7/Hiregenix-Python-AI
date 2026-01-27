import os
import json
import pika
import traceback
from utils.constant import AUDIO_ANALYSIS_QUEUE
from config.db import task_collection, question_result_collection
from bson import ObjectId
from dotenv import load_dotenv

load_dotenv()

RABBITMQ_URL = os.getenv("RABBITMQ_URL")

# --- Setup RabbitMQ Connection ---
params = pika.URLParameters(RABBITMQ_URL)
connection = pika.BlockingConnection(params)
channel = connection.channel()
channel.queue_declare(queue=AUDIO_ANALYSIS_QUEUE, durable=True)
channel.confirm_delivery()


def callback(ch, method, properties, body):
    task_id = body.decode()
    print(f"📥 Received Task {task_id}")
    
    try:
        task = task_collection.find_one({"_id": ObjectId(task_id)})
        if not task:
            print(f"❌ Task {task_id} not found")
            ch.basic_ack(delivery_tag=method.delivery_tag)
            return
        
        print(f" 🔍 Fetched Task {task} from DB: {task}")
        task_collection.update_one(
            {"_id": ObjectId(task_id)}, {"$set": {"status": "processing"}}
        )
        candidate_id=task['userId'];
        print(f"⏳ Task {task_id} status updated to processing")
    
        # fetching the question result id for fetching the question result document
        question_result_id = task["payload"]["questionResultId"]

        
        # --- Mark Task as Completed ---
        task_collection.update_one(
            {"_id": ObjectId(task_id)},
            {"$set": {"status": "completed", "error": None}},
        )
        print(f"✅ Task {task_id} completed successfully")
        # Acknowledge successful message
        # ch.basic_ack(delivery_tag=method.delivery_tag)
    
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



# --- Start Consuming Messages ---
channel.basic_qos(prefetch_count=1)  # Fair dispatch
channel.basic_consume(
    queue=AUDIO_ANALYSIS_QUEUE,
    on_message_callback=callback,
    auto_ack=False  # Manual ack ensures reliability
)

print("🚀 Worker started and waiting for speech to text jobs...")
try:
    channel.start_consuming()
except KeyboardInterrupt:
    print("👋 Worker stopped manually")
    channel.stop_consuming()
    connection.close()
