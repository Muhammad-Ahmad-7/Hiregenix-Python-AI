from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Literal
from datetime import datetime
from bson import ObjectId

# Helper for ObjectId handling in MongoDB documents
class PyObjectId(ObjectId):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate
    
    @classmethod
    def validate(cls, v):
        if isinstance(v, ObjectId):
            return v
        if isinstance(v, str):
            try:
                return ObjectId(v)
            except Exception:
                raise ValueError("Invalid ObjectId format")
        raise TypeError("ObjectId must be str or ObjectId instance")

# Subschemas
class Location(BaseModel):
    city: Optional[str] = None
    country: Optional[str] = None

class SalaryRange(BaseModel):
    min: Optional[float] = None
    max: Optional[float] = None
    currency: Optional[str] = None

# Main Job Schema
class Job(BaseModel):
    id: Optional[PyObjectId] = Field(default=None, alias="_id")
    companyId: PyObjectId = Field(..., description="Reference to company")
    title: str
    role: str
    interviewGuideline: str
    experienceLevel: Literal["entry", "mid", "senior"]
    description: str
    requiredSkills: List[str]
    requirements: Optional[List[str]] = None
    workMode: Literal["full-time", "part-time", "remote"]
    location: Optional[Location] = None
    salaryRange: Optional[SalaryRange] = None
    aiSummary: Optional[str] = Field(default="")
    embeddingSynced: Optional[bool] = Field(default=False)
    qdrantId: Optional[str] = Field(default=None)
    status: Literal["open", "closed"] = Field(default="open")
    createdAt: Optional[datetime] = None
    updatedAt: Optional[datetime] = None

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str},
    )
