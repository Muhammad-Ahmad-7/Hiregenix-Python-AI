from config.db import job_collection
from bson import ObjectId
from pydantic import BaseModel
from langchain.output_parsers import PydanticOutputParser
from prompts.company import JOB_POSTING_DESCRIPTION_PROMPT
from config.env import OPENAI_API_KEY
from langchain.prompts import ChatPromptTemplate
from utils.qdrant import connection_qdrant, create_qdrant_collection
from utils.embeddings import get_gemini_embedding, get_huggingface_embedding
from qdrant_client.models import PointStruct
import os
import json
import pika
import traceback
from utils.constant import JOB_DESCRIPTION_EMBEDDINGS_QUEUE
from config.db import task_collection
from bson import ObjectId
from dotenv import load_dotenv
from qdrant_client import QdrantClient
import uuid
from pymongo import ReturnDocument
from utils.llm_call import get_llm_model



class ParsedDescription(BaseModel):
    aiDescription: str


parser = PydanticOutputParser(pydantic_object=ParsedDescription)


def generate_job_post_ai_description(job_id):
    
    try:
        job = job_collection.find_one({"_id": ObjectId(job_id)})
    
        if not job:
            print("❌ Job not found in DB")
            return
        
        print(f" 🔍 Fetched Job {job_id} from DB: {job}")
        
        title=job['title']
        role=job['role']
        description=job['description']
        required_skills=job['requiredSkills']
        requirements = job['requirements']
        
        print("Generating AI Description")
        # model = init_chat_model(
        #     model_provider='google_genai',
        #     model='gemini-2.5-flash',
        #     api_key=OPENAI_API_KEY
        # )
        
        model = get_llm_model()
        # Create the prompt template
        prompt_template = ChatPromptTemplate.from_messages([
            ("system", JOB_POSTING_DESCRIPTION_PROMPT),
            ("human", "Please write a brief description based on title: {title}, role: {role}, description: {description}, required skills: {required_skills}, requirements: {requirements}")
        ])

        print("Prompt template created")

        # ✅ Correct way: use .format_messages, not .format
        messages = prompt_template.format_messages(
            title=title,
            role=role,
            description=description,
            required_skills=required_skills,
            requirements=requirements,
            format_instructions=parser.get_format_instructions()
        )
        
        print(f"Messages created {messages}")

        # Invoke model
        result = model.invoke(messages)

        # Parse and display
        parsed_output = parser.parse(result.content)
        result = parsed_output.model_dump()

        print(f"🤖 AI Description generated: {result}")
        description = result.get('aiDescription')
        
        # update the job
        
        updated_job = job_collection.find_one_and_update(
            {"_id": ObjectId(job_id)},
            {"$set": {"aiSummary": description}},
            return_document=ReturnDocument.AFTER,  # ✅ ensures you get the updated doc
            upsert=True
        )
        
        print(f"Job updated with AI description: {updated_job}")
        
        # Generate Embeddings for the candidate
        generate_embeddings(job=updated_job);
        return True
    except Exception as e:
        print(f"❌ Error processing job {job_id}: {e}")
        return False



def generate_embeddings(job):
    try:
        print("Generating Embeddings")
        client = connection_qdrant()
        client = create_qdrant_collection(client, "job")
        
        description = job.get('aiSummary')
        
        # embeddings = get_gemini_embedding(description)
        embeddings = get_huggingface_embedding(description)
        
        qdrant_id = str(uuid.uuid4())
        
        client.upsert(
            collection_name="job",
            points=[
                PointStruct(
                    id=qdrant_id,
                    vector=embeddings,
                    payload={
                        "job_id": str(job.get('_id')),
                        "aiSummary": job.get('aiSummary')
                    }
                )
            ]
        )
        
        updated_job = job_collection.find_one_and_update(
            {"_id": ObjectId(job.get('_id'))},
            {"$set": {"embeddingSynced": True, "qdrantId": qdrant_id}},
            return_document=ReturnDocument.AFTER,  # ✅ ensures you get the updated doc
            upsert=True
        )
        print(f"Embeddings generated and stored {updated_job}")
        return True
    except Exception as e:
        print(f"❌ Error generating embeddings: {e}")
        return False