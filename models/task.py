from typing import Optional, Dict, Any, Literal
from pydantic import BaseModel, Field
from bson import ObjectId
from datetime import datetime

class PyObjectId(ObjectId):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate
    
    @classmethod
    def validate(cls, v):
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid ObjectId")
        return ObjectId(v)

class TaskModel(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id")
    userId: PyObjectId
    type: Literal["resume_parsing", "profile_enhancement", "resume_feedback", "interview_prep", "candidate_profile_embeddings", "job_description_embeddings", "job_recommendation", "speech_to_text", "audio_analysis", "video_analysis", "llm_evaluation", "final_interview_evaluation", "report_generation_pdf"]
    payload: Dict[str, Any]
    retryCount: int = 0
    status: Literal["pending", "processing", "completed", "failed"] = "pending"
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    createdAt: Optional[datetime] = None
    updatedAt: Optional[datetime] = None

    class Config:
        json_encoders = {ObjectId: str}
        arbitrary_types_allowed = True
