
import os
import time
import json
import traceback
import pika
from utils.constant import RESUME_ANALYSIS_QUEUE
from config.db import task_collection
from bson import ObjectId
from dotenv import load_dotenv
load_dotenv()

from ai_modules.resume_parser import get_resume_parsing_graph


RABBITMQ_URL = os.getenv("RABBITMQ_URL")


params = pika.URLParameters(RABBITMQ_URL)
connection = pika.BlockingConnection(params)
channel = connection.channel()

channel.queue_declare(queue=RESUME_ANALYSIS_QUEUE, durable=True)

def callback(ch, method, properties, body):
    task_id = body.decode()
    print(f"📥 Received Task {task_id}")
    
    try:
        
        task = task_collection.find_one({"_id": ObjectId(task_id)})
        
        print(f" 🔍 Fetched Task {task_id} from DB: {task}")
        if not task:
            print("❌ Task not found in DB")
            return
        task_collection.update_one({"_id": ObjectId(task_id)}, {"$set": {"status": "processing"}})
        print(f"⏳ Task {task_id} status updated to processing")
        resume_url = task['payload']['resume']

        graph = get_resume_parsing_graph()
        
        graph.invoke({
            "resume_url": resume_url,
            "candidate_id": str(task['userId'])
        })

        task_collection.update_one({"_id": ObjectId(task_id)}, {"$set": {"status": "completed"}})
        print(f"✅ Task {task_id} completed")

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

channel.basic_consume(queue=RESUME_ANALYSIS_QUEUE, on_message_callback=callback, auto_ack=False) # auto_ack=True to auto acknowledge when worker is done processing the message

print("🚀 Worker started and waiting for resume parsing jobs...")
try:
    channel.start_consuming()
except KeyboardInterrupt:
    print("👋 Worker stopped manually")
    channel.stop_consuming()
    connection.close()