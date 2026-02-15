import os
import json
import pika
import traceback
from utils.constant import FINAL_INTERVIEW_EVAL_QUEUE, REPORT_GENERATION_PDF_QUEUE
from config.db import task_collection
from ai_modules.final_eval import final_interview_pipeline
from bson import ObjectId
from dotenv import load_dotenv


load_dotenv()

RABBITMQ_URL = os.getenv("RABBITMQ_URL")

# --- Setup RabbitMQ Connection ---
params = pika.URLParameters(RABBITMQ_URL)
connection = pika.BlockingConnection(params)
channel = connection.channel()
channel.queue_declare(queue=FINAL_INTERVIEW_EVAL_QUEUE, durable=True)
channel.queue_declare(queue=REPORT_GENERATION_PDF_QUEUE, durable=True)
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
            print("❌ Task creation failed")
            return False
        print(f"✅ Task created successfully with ID: {result.inserted_id}")
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
        
        print("Delivered", delivered)
        print(f"📤 Enqueued report generation pdf evaluation task {result.inserted_id} for question result {report_id}")
        return True
    except pika.exceptions.AMQPChannelError as e:
        print(f"Error: {e}")
        # Handle channel errors, e.g., if the message was nack-ed or unroutable
    except Exception as e:
        print(f"❌ Error creating and pushing llm evaluation task: {e}")
        return False

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

        print(f" 🔍 Fetched Task {task} from DB: {task}")
        task_collection.update_one(
            {"_id": ObjectId(task_id)}, {"$set": {"status": "processing"}}
        )
        candidate_id=task['userId'];
        print(f"⏳ Task {task_id} status updated to processing")
        
        interview_id = task["payload"]["interview_id"]
        
        result = final_interview_pipeline(interview_id=interview_id)
        
        if not result:
            print("Acknowledge the task because interview does not exist")
            # ch.basic_nack(delivery_tag=method.delivery_tag)
        
        report_id = result
        
        res = create_and_push_report_generation_pdf_task_to_queue(report_id=report_id, candidate_id=candidate_id)
        
        print(f"✅ Task {task_id} final interview evaluation processing completed successfully")
        
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
    queue=FINAL_INTERVIEW_EVAL_QUEUE,
    on_message_callback=callback,
    auto_ack=False  # Manual ack ensures reliability
)

print("🚀 Worker started and waiting for final interview evaluation jobs...")
try:
    channel.start_consuming()
except KeyboardInterrupt:
    print("👋 Worker stopped manually")
    channel.stop_consuming()
    connection.close()