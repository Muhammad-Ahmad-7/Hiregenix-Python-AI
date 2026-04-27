import logging
import tempfile
import traceback
from bson import ObjectId
import requests
import pika

from pymongo import ReturnDocument
from langchain.text_splitter import RecursiveCharacterTextSplitter
from pypdf import PdfReader

from config.db import task_collection
from utils.rabbitmq import connect_rabbitmq, initialize_queues
from utils.logger_config import setup_logging
from utils.constant import (
    COMPANY_KB_EMBEDDINGS_QUEUE,
    FAILED_COMPANY_KB_EMBEDDINGS_TASK_QUEUE,
)
from utils.embeddings import get_huggingface_embedding
from utils.qdrant import connection_qdrant, create_qdrant_collection

setup_logging("logger/company_kb_embeddings_worker.log")
logger = logging.getLogger(__name__)


channel, connection = connect_rabbitmq()
channel = initialize_queues(channel=channel)
channel.confirm_delivery()


def _download_pdf(url: str) -> str:
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    fd, path = tempfile.mkstemp(suffix=".pdf")
    with open(path, "wb") as f:
        f.write(r.content)
    return path


def _extract_text(pdf_path: str) -> str:
    reader = PdfReader(pdf_path)
    parts = []
    for i, page in enumerate(reader.pages):
        try:
            txt = page.extract_text() or ""
        except Exception:
            txt = ""
        if txt.strip():
            parts.append(txt)
    return "\n\n".join(parts)


def callback(ch, method, properties, body):
    task_id = body.decode()
    logger.info("Task received | task_id=%s", task_id)

    if not ObjectId.is_valid(task_id):
        ch.basic_ack(delivery_tag=method.delivery_tag)
        return

    try:
        task = task_collection.find_one_and_update(
            {"_id": ObjectId(task_id), "status": "pending"},
            {"$set": {"status": "processing"}},
        )
        if not task:
            ch.basic_ack(delivery_tag=method.delivery_tag)
            return

        payload = task.get("payload", {}) or {}
        company_id = payload.get("companyId")
        pdf_url = payload.get("pdfUrl")
        collection_name = payload.get("collectionName") or (f"company_kb_{company_id}" if company_id else None)

        if not company_id or not pdf_url or not collection_name:
            raise Exception("Missing companyId/pdfUrl/collectionName in task payload")

        pdf_path = _download_pdf(pdf_url)
        text = _extract_text(pdf_path)
        if not text.strip():
            raise Exception("PDF contains no extractable text")

        splitter = RecursiveCharacterTextSplitter(chunk_size=900, chunk_overlap=150)
        chunks = splitter.split_text(text)
        if not chunks:
            raise Exception("No chunks generated from PDF text")

        qdrant = connection_qdrant()
        create_qdrant_collection(qdrant, collection_name)

        points = []
        for idx, chunk in enumerate(chunks):
            vector = get_huggingface_embedding(chunk)
            points.append(
                {
                    "id": idx + 1,
                    "vector": vector,
                    "payload": {
                        "companyId": str(company_id),
                        "chunkIndex": idx,
                        "text": chunk,
                        "pdfUrl": pdf_url,
                        "taskId": task_id,
                    },
                }
            )

        qdrant.upsert(collection_name=collection_name, points=points)

        task_collection.update_one(
            {"_id": ObjectId(task_id)},
            {
                "$set": {
                    "status": "completed",
                    "error": None,
                    "result": {
                        "companyId": str(company_id),
                        "collectionName": collection_name,
                        "chunks": len(chunks),
                        "pdfUrl": pdf_url,
                    },
                }
            },
        )

        ch.basic_ack(delivery_tag=method.delivery_tag)
        logger.info("KB embeddings completed | task_id=%s | chunks=%s", task_id, len(chunks))

    except Exception as e:
        logger.error("Task crashed | task_id=%s | err=%s", task_id, str(e))
        logger.debug(traceback.format_exc())

        updated_task = task_collection.find_one_and_update(
            {"_id": ObjectId(task_id)},
            {"$set": {"status": "failed", "error": str(e)}, "$inc": {"retryCount": 1}},
            return_document=ReturnDocument.AFTER,
        )
        retry_count = updated_task.get("retryCount", 0) if updated_task else 999
        if retry_count >= 3:
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
        else:
            # simple requeue for retry (no delay queue wired for this worker yet)
            task_collection.update_one(
                {"_id": ObjectId(task_id)},
                {"$set": {"status": "pending", "error": None}},
            )
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)


channel.basic_qos(prefetch_count=1)
channel.basic_consume(
    queue=COMPANY_KB_EMBEDDINGS_QUEUE,
    on_message_callback=callback,
    auto_ack=False,
)

logger.info("Worker started and waiting for company KB embedding jobs...")
try:
    channel.start_consuming()
except KeyboardInterrupt:
    logger.info("Worker stopped manually")
    channel.stop_consuming()
    connection.close()

