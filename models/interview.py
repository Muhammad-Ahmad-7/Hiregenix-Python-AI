from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional
from datetime import datetime
from bson import ObjectId
from pydantic_core import core_schema
from enum import Enum

# ---- Helper for ObjectId ----
class PyObjectId(ObjectId):
    @classmethod
    def __get_pydantic_core_schema__(cls, _source_type, _handler):
        return core_schema.union_schema([
            core_schema.is_instance_schema(ObjectId),
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

# ---- Enum for interview status ----
class InterviewStatus(str, Enum):
    pending = "pending"
    scheduled = "scheduled"
    in_progress = "in-progress"
    completed = "completed"
    missed = "missed"
    no_show = "no-show"
    cancelled = "cancelled"
    expired = "expired"

# ---- Main Interview Model ----
class Interview(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    candidateId: PyObjectId = Field(..., description="FK to Candidate")
    companyId: PyObjectId = Field(..., description="FK to Company")
    jobId: PyObjectId = Field(..., description="FK to Job")
    type: str = Field(default="live")
    
    scheduledDate: Optional[datetime] = None
    durationMins: Optional[int] = None
    
    status: InterviewStatus = Field(default=InterviewStatus.pending)
    
    questions: List[str] = Field(
        default_factory=lambda: [
            "Explain the difference between authentication and authorization in a web application.",
            "Describe what happens from the moment a user types a URL into their browser until the page loads.",
            "What are the primary differences between a REST API and GraphQL?",
            "Define 'Idempotency' in the context of HTTP methods and why it matters for API design.",
            "What is a deadlock in a database, and how can a developer prevent one from occurring.",
            "Explain the concept of 'Horizontal Scaling' versus 'Vertical Scaling' for a server.",
            "What is the purpose of a Message Queue like RabbitMQ or Kafka in a distributed system?",
            "Describe the role of an ORM and name one potential disadvantage of using it.",
            "What are 'Indexes' in a database and how do they speed up read operations?",
            "What is the difference between a 'Stateful' and a 'Stateless' service architecture?",
            "What is a 'Rate Limiter' and why is it important for public-facing APIs?",
            "Explain the concept of 'Graceful Degradation' in backend services."
        ]
    )
    
    totalQuestions: int = Field(default=10)
    completedQuestions: int = Field(default=0)
    reportId: Optional[PyObjectId] = None  # FK to FinalInterviewReport
    
    createdAt: Optional[datetime] = Field(default_factory=datetime.utcnow)
    updatedAt: Optional[datetime] = Field(default_factory=datetime.utcnow)
