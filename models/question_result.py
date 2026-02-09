from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional
from datetime import datetime
from bson import ObjectId
from pydantic_core import core_schema
from enum import Enum

# ---- Helper to handle ObjectId safely ----
class PyObjectId(ObjectId):
    @classmethod
    def __get_pydantic_core_schema__(cls, _source_type, _handler):
        return core_schema.union_schema([
            core_schema.is_instance_schema(ObjectId),  # allow ObjectId directly
            core_schema.no_info_after_validator_function(cls.validate, core_schema.str_schema())
        ])

    @classmethod
    def validate(cls, v, _info=None):
        if isinstance(v, ObjectId):
            return v
        try:
            return ObjectId(v)
        except Exception:
            raise ValueError(f"Invalid ObjectId: {v}")

# ---- Enum for status ----
class QuestionResultStatus(str, Enum):
    PROCESSING = 'PROCESSING'
    DONE = 'DONE'
    FAILED = 'FAILED'

# ---- Nested Models ----
class Scores(BaseModel):
    content: Optional[float] = None
    communication: Optional[float] = None
    skill: Optional[float] = None
    overall: Optional[float] = None

class LLMAnalysis(BaseModel):
    confidenceScore: Optional[float] = None
    missingConcepts: Optional[List[str]] = None
    summary: Optional[str] = None
    notes: Optional[str] = None

class Stages(BaseModel):
    uploaded: bool = False
    audioExtracted: bool = False
    sttDone: bool = False
    videoAnalyzed: bool = False
    audioAnalyzed: bool = False
    llmEvaluated: bool = False
    done: bool = False
    failed: bool = False

# ---- Main Model ----
class QuestionResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)  # allow .dict() from ORM/attrs
    
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    interviewId: PyObjectId = Field(..., description="FK to the Interview document")
    questionId: str = Field(..., description="Question id from question bank")
    questionText: str = Field(..., description="Snapshot of question at the time of interview")
    
    candidateAnswer: Optional[str] = None    
    sttData: Optional[dict] = None
    videoUrl: Optional[str] = None
    audioUrl: Optional[str] = None
    videoAnalysis: Optional[dict] = None
    audioAnalysis: Optional[dict] = None
    lLMAnalysis: Optional[dict] = None
    
    scores: Optional[Scores] = None
    
    status: QuestionResultStatus = QuestionResultStatus.PROCESSING
    stages: Stages = Field(default_factory=Stages, description="Stages of processing")
    llmEnqueued: bool = False
    llmStartedAt: Optional[datetime] = None
    llmCompletedAt: Optional[datetime] = None
    
    createdAt: Optional[datetime] = Field(default_factory=datetime.utcnow, description="Document creation timestamp")
    updatedAt: Optional[datetime] = Field(default_factory=datetime.utcnow, description="Document update timestamp")
