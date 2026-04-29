from typing import List
from langchain.prompts import ChatPromptTemplate
from prompts.candidate import PROFILE_DESCRIPTION_PROMPT
from langchain.output_parsers import PydanticOutputParser
from pydantic import BaseModel
from config.db import candidate_collection
from pymongo import ReturnDocument
from bson import ObjectId
from utils.llm_call import get_llm_model
from utils.qdrant import connection_qdrant, create_qdrant_collection
from utils.embeddings import get_gemini_embedding, get_huggingface_embedding
from qdrant_client.models import PointStruct

import uuid

class ParsedDescription(BaseModel):
    aiDescription: str


parser = PydanticOutputParser(pydantic_object=ParsedDescription)


def generate_candidate_profile_ai_description(candidate_id: str, skills: List[str], bio: str):
    print("Generating AI Description")
    # model = init_chat_model(
    #     model_provider='google_genai',
    #     model='gemini-2.5-flash',
    #     api_key=OPENAI_API_KEY
    # )
    
    model = get_llm_model("openai/gpt-oss-20b")
    print(f"received skills {skills} and bio {bio}")

    # Create the prompt template
    prompt_template = ChatPromptTemplate.from_messages([
        ("system", PROFILE_DESCRIPTION_PROMPT),
        ("human", "Please write a brief description based on skills: {skills} and bio: {bio}")
    ])

    print("Prompt template created")

    # ✅ Correct way: use .format_messages, not .format
    messages = prompt_template.format_messages(
        skills=skills,
        bio=bio,
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
    
    # update the candidate
    
    updated_candidate = candidate_collection.find_one_and_update(
        {"_id": ObjectId(candidate_id)},
        {"$set": {"aiDescription": description}},
        return_document=ReturnDocument.AFTER,  # ✅ ensures you get the updated doc
        upsert=True
    )
    
    print(f"Candidate updated with AI description: {updated_candidate}")
    
    # Generate Embeddings for the candidate
    generate_embeddings(candidate=updated_candidate);
    
    
    return description




def generate_embeddings(candidate):
    print("Generating Embeddings")
    client = connection_qdrant()
    client = create_qdrant_collection(client, "candidate")
    
    description = candidate.get('aiDescription')
    
    # embeddings = get_gemini_embedding(description)
    embeddings = get_huggingface_embedding(description)
    print(type(embeddings), len(embeddings))
    
    qdrant_id = str(uuid.uuid4())
    
    client.upsert(
        collection_name="candidate",
        points=[
            PointStruct(
                id=qdrant_id,
                vector=embeddings,
                payload={
                    "candidate_id": str(candidate.get('_id')),
                    "description": candidate.get('aiDescription')
                }
            )
        ]
    )
    
    updated_candidate = candidate_collection.find_one_and_update(
        {"_id": ObjectId(candidate.get('_id'))},
        {"$set": {"embeddingSync": True, "qdrantId": qdrant_id}},
        return_document=ReturnDocument.AFTER,  # ✅ ensures you get the updated doc
        upsert=True
    )
    print(f"Embeddings generated and stored {updated_candidate}")
    return




















# {'_id': ObjectId('68e22d477fe78b84f0876cdd'), 'userId': ObjectId('68e22d137fe78b84f0876cd9'), 'fullName': 'Muhammad Ahmad', 'dateOfBirth': datetime.datetime(2003, 7, 19, 0, 0), 'gender': 'male', 'country': 'Pakistan', 'city': 'Lahore', 'contactNumber': '+923001234560', 'profilePictureUrl': 'https://example.com/uploads/profile123.jpg', 'githubUrl': 'https://github.com/ahmad-dev', 'linkedinUrl': 'https://www.linkedin.com/in/ahmad-dev', 'portfolioUrl': 'https://ahmad-portfolio.com', 'skills': ['React', 'Next.js', 'Node.js', 'MongoDB', 'TypeScript'], 'bio': 'Full Stack Developer with SaaS and AI integration expertise.', 'tagline': 'Building scalable web apps with modern tech', 'resumeId': None, 'isProfileCompleted': False, 'isDeleted': 'false', 'createdAt': datetime.datetime(2025, 10, 5, 8, 33, 11, 872000), 'updatedAt': datetime.datetime(2025, 10, 5, 8, 39, 19, 854000), '__v': 0}