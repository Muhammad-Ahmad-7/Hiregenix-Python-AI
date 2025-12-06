from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional
from datetime import datetime
from bson import ObjectId


# ---- Helper to handle ObjectId safely ----

class PyObjectId(ObjectId):
    @classmethod
    def __get_pydantic_core_schema__(cls, _source_type, _handler):
        from pydantic_core import core_schema
        return core_schema.union_schema([
            core_schema.is_instance_schema(ObjectId),  # ✅ allow ObjectId directly
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


# ---- Submodel for each recommended job ----
class JobLocation(BaseModel):
    city: Optional[str] = Field(None, description="City of the job location")
    country: Optional[str] = Field(None, description="Country of the job location")


class SalaryRange(BaseModel):
    min: Optional[int] = Field(None, description="Minimum salary")
    max: Optional[int] = Field(None, description="Maximum salary")
    currency: Optional[str] = Field(None, description="Currency of salary")


class RecommendedJobItem(BaseModel):
    jobId: str = Field(..., description="Unique identifier for the job")
    title: str = Field(..., description="Job title")
    role: str = Field(..., description="Job role or specialization")

    companyName: str = Field(..., description="Company name")
    companyLogo: str = Field(..., description="Company logo URL")

    workMode: str = Field(..., description="full-time | part-time | remote")

    requiredSkills: Optional[List[str]] = Field(None)
    requirements: Optional[List[str]] = Field(None)
    description: Optional[str] = Field(None)

    location: Optional[JobLocation] = Field(None, description="Job location object")

    salaryRange: Optional[SalaryRange] = Field(None, description="Salary range")

    aiSummary: Optional[str] = Field("", description="AI-generated job summary")

    createdAt: Optional[datetime] = Field(default_factory=datetime.utcnow)
    updatedAt: Optional[datetime] = Field(default_factory=datetime.utcnow)


# ---- Main model for Recommended Jobs ----
class RecommendedJobs(BaseModel):
    id: Optional[PyObjectId] = Field(default=None, alias="_id")
    candidateId: PyObjectId = Field(..., description="Candidate ObjectId reference")
    recommendedJobs: List[RecommendedJobItem] = Field(default_factory=list, description="List of recommended job entries")
    createdAt: Optional[datetime] = Field(default_factory=datetime.utcnow, description="Document creation timestamp")
    updatedAt: Optional[datetime] = Field(default_factory=datetime.utcnow, description="Document update timestamp")

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str}
    )
