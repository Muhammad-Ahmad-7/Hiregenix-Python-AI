import os
import json
import pika
import traceback
from utils.constant import SPEECH_TO_TEXT_QUEUE, AUDIO_ANALYSIS_QUEUE, VIDEO_ANALYSIS_QUEUE
from config.db import task_collection, question_result_collection
from bson import ObjectId
from dotenv import load_dotenv
from ai_modules.stt import speech_to_text_pipeline

load_dotenv()

RABBITMQ_URL = os.getenv("RABBITMQ_URL")

# --- Setup RabbitMQ Connection ---
params = pika.URLParameters(RABBITMQ_URL)
connection = pika.BlockingConnection(params)
channel = connection.channel()
channel.queue_declare(queue=SPEECH_TO_TEXT_QUEUE, durable=True)
channel.queue_declare(queue=AUDIO_ANALYSIS_QUEUE, durable=True)
channel.queue_declare(queue=VIDEO_ANALYSIS_QUEUE, durable=True)
channel.confirm_delivery()



def create_and_push_audio_analysis_task_to_queue(question_result_id: str, candidate_id: str) -> ObjectId:
    """Create a new audio analysis task document and push it to the audio analysis queue."""
    try:
        doc = {
            "userId": candidate_id,
            "type": "audio_analysis",
            "status": "pending",
            "payload": {
                "questionResultId": question_result_id,
            },
        }
        result = task_collection.insert_one(doc)
        if not result.acknowledged or not result.inserted_id:
            print("❌ Task creation failed")
            return False
        print(f"✅ Task created successfully with ID: {result.inserted_id}")
        body = str(result.inserted_id).encode()
        channel.basic_publish(
            exchange='',
            routing_key=AUDIO_ANALYSIS_QUEUE,
            body=body,
            properties=pika.BasicProperties(
                delivery_mode=pika.DeliveryMode.Persistent,
            ),
            mandatory=True  # raise on unroutable
        )
        print(f"📤 Enqueued audio analysis task {result.inserted_id} for question result {question_result_id}")
        return True
    except Exception as e:
        print(f"❌ Error creating and pushing audio analysis task: {e}")
        return False


def create_and_push_video_analysis_task_to_queue(question_result_id: str, candidate_id: str) -> ObjectId:
    """Create a new video analysis task document and push it to the video analysis queue."""
    try:
        doc = {
            "userId": candidate_id,
            "type": "video_analysis",
            "status": "pending",
            "payload": {
                "questionResultId": question_result_id,
            },
        }
        result = task_collection.insert_one(doc)
        if not result.acknowledged or not result.inserted_id:
            print("❌ Task creation failed")
            return False
        print(f"✅ Task created successfully with ID: {result.inserted_id}")
        body = str(result.inserted_id).encode()
        channel.basic_publish(
            exchange='',
            routing_key=VIDEO_ANALYSIS_QUEUE,
            body=body,
            properties=pika.BasicProperties(
                delivery_mode=pika.DeliveryMode.Persistent,
            ),
            mandatory=True  # raise on unroutable
        )
        print(f"📤 Enqueued video analysis task {result.inserted_id} for question result {question_result_id}")
        return True
    except Exception as e:
        print(f"❌ Error creating and pushing video analysis task: {e}")
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
        
        # fetching the question result id for fetching the question result document
        question_result_id = task["payload"]["questionResultId"]
        
        # speech to text  processing logic goes here
        result = speech_to_text_pipeline(question_result_id)
        if not result:
            print("Acknowledge the task because question does not exist")
            ch.basic_ack(delivery_tag=method.delivery_tag)
        
        print(f"✅ Task {task_id} speech to text processing completed successfully")
        
        # push the question_result_id in the video analysis queue and audio analysis queue for next work.
        
        audio_analysis_queue_result = create_and_push_audio_analysis_task_to_queue(question_result_id, candidate_id)
        
        
        if not audio_analysis_queue_result:
            raise Exception("Audio analysis task not created in DB")
        
        print(f"✅ Task {task_id} audio analysis task created successfully")
        
        video_analysis_queue_result = create_and_push_video_analysis_task_to_queue(question_result_id=question_result_id, candidate_id=candidate_id)
        
        if not video_analysis_queue_result:
            raise Exception("Video analysis task not created in DB")
        
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
    queue=SPEECH_TO_TEXT_QUEUE,
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