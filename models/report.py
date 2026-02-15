from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field, field_validator
from bson import ObjectId


# Helper to allow ObjectId fields in Pydantic
class PyObjectId(ObjectId):

    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if not v:
            return ObjectId()  # auto-generate if None
        if isinstance(v, ObjectId):
            return v
        try:
            return ObjectId(str(v))
        except Exception:
            raise ValueError("Invalid ObjectId")


class Score(BaseModel):
    contentScore: Optional[int] = None
    communicationScore: Optional[int] = None
    fluencyScore: Optional[int] = None
    confidenceScore: Optional[int] = None
    overallScore: Optional[int] = None


class Integrity(BaseModel):
    integrityConcern: Optional[bool] = False
    integrityNotes: Optional[str] = None


class FinalInterviewReport(BaseModel):
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    interviewId: PyObjectId

    overallScore: Optional[Score] = None
    overallAnswerQuality: Optional[str] = None
    overallInterviewScore: Optional[int] = None

    topStrengths: List[str] = []
    topWeaknesses: List[str] = []
    commonMissingConcepts: List[str] = []
    overallImprovementSuggestions: List[str] = []

    integrity: Optional[Integrity] = Integrity()
    interviewSummary: Optional[str] = None
    pdfUrl: Optional[str] = None

    createdAt: datetime = Field(default_factory=datetime.now)
    updatedAt: datetime = Field(default_factory=datetime.now)

    class Config:
        allow_population_by_field_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}

    @field_validator("updatedAt", pre=True, always=True)
    def set_updated_at(cls, v):
        return v or datetime.now()
