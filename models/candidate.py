from typing import List, Optional, Any, Literal
from pydantic import BaseModel, Field, field_validator
from pydantic_core import core_schema
from bson import ObjectId
from datetime import datetime


# ---------------------------
# Helper for ObjectId
# ---------------------------
class PyObjectId(ObjectId):
    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: Any, handler
    ) -> core_schema.CoreSchema:
        return core_schema.union_schema([
            core_schema.is_instance_schema(ObjectId),
            core_schema.no_info_plain_validator_function(cls.validate),
        ])

    @classmethod
    def validate(cls, v):
        if isinstance(v, ObjectId):
            return v
        if isinstance(v, str) and ObjectId.is_valid(v):
            return ObjectId(v)
        raise ValueError("Invalid ObjectId")

    def __str__(self):
        return str(super())


# ---------------------------
# Main Candidate Model
# ---------------------------
class CandidateModel(BaseModel):
    model_config = {
        "arbitrary_types_allowed": True,
        "json_encoders": {
            ObjectId: str,
            datetime: lambda dt: dt.isoformat() if dt else None
        }
    }

    id: Optional[PyObjectId] = Field(default=None, alias="_id")
    userId: Optional[PyObjectId] = None
    fullName: Optional[str] = None
    dateOfBirth: Optional[datetime] = None
    gender: Optional[Literal["male", "female", "other"]] = None
    contactNumber: Optional[str] = None
    profilePictureUrl: Optional[str] = None
    bio: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    githubUrl: Optional[str] = None
    linkedinUrl: Optional[str] = None
    portfolioUrl: Optional[str] = None
    resumeId: Optional[PyObjectId] = None
    skills: List[str] = Field(default_factory=list)
    isProfileCompleted: bool = False
    tagline: Optional[str] = None
    isDeleted: Optional[str] = Field(default="false")
    aiDescription: Optional[str] = None
    embeddingSync: Optional[bool] = False
    qdrantId: Optional[str] = None
    createdAt: Optional[datetime] = None
    updatedAt: Optional[datetime] = None

    @field_validator("skills", mode="before")
    @classmethod
    def validate_skills(cls, v):
        if v is None:
            return []
        if isinstance(v, list):
            return v
        return []

