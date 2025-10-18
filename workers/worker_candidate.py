import os
import json
import pika
import traceback
from utils.constant import CANDIDATE_PROFILE_EMBEDDINGS_QUEUE, JOB_RECOMMENDATION_QUEUE
from ai_modules.candidate import generate_candidate_profile_ai_description
from config.db import candidate_collection, task_collection
from bson import ObjectId
from dotenv import load_dotenv
from qdrant_client import QdrantClient

load_dotenv()

RABBITMQ_URL = os.getenv("RABBITMQ_URL")

# --- Setup RabbitMQ Connection ---
params = pika.URLParameters(RABBITMQ_URL)
connection = pika.BlockingConnection(params)
channel = connection.channel()
channel.queue_declare(queue=CANDIDATE_PROFILE_EMBEDDINGS_QUEUE, durable=True)
channel.queue_declare(queue=JOB_RECOMMENDATION_QUEUE, durable=True);


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
    return result.inserted_id



def publish_recommendation_task(task_id: ObjectId):
    """Publish the recommendation task id to JOB_RECOMMENDATION_QUEUE with persistence."""
    body = str(task_id).encode()
    channel.basic_publish(
        exchange='',
        routing_key=JOB_RECOMMENDATION_QUEUE,
        body=body,
        properties=pika.BasicProperties(
            delivery_mode=pika.DeliveryMode.Persistent,
        ),
        mandatory=True  # raise on unroutable
    )

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

        candidate_id = task["payload"]["candidateId"]
        candidate = candidate_collection.find_one({"_id": ObjectId(candidate_id)})

        if not candidate:
            print("❌ Candidate not found in DB")
            ch.basic_ack(delivery_tag=method.delivery_tag)
            return

        print(f" 🔍 Fetched Candidate {candidate_id} from DB: {candidate}")

        skills = candidate.get("skills", [])
        bio = candidate.get("bio", "")

        # --- Generate Description ---
        generate_candidate_profile_ai_description(candidate_id=candidate_id, skills=skills, bio=bio)

        # --- Mark Task as Completed ---
        task_collection.update_one(
            {"_id": ObjectId(task_id)},
            {"$set": {"status": "completed", "error": None}},
        )
        print(f"✅ Task {task_id} completed successfully")
        
        rec_task_id = create_recommendation_task(candidate_id=candidate_id)
        publish_recommendation_task(rec_task_id)
        print(f"📤 Enqueued recommendation task {rec_task_id} for candidate {candidate_id}")

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
    queue=CANDIDATE_PROFILE_EMBEDDINGS_QUEUE,
    on_message_callback=callback,
    auto_ack=False  # Manual ack ensures reliability
)

print("🚀 Worker started and waiting for candidate profile embedding jobs...")
try:
    channel.start_consuming()
except KeyboardInterrupt:
    print("👋 Worker stopped manually")
    channel.stop_consuming()
    connection.close()