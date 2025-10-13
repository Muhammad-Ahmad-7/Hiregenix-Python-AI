from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional
from datetime import datetime
from bson import ObjectId


# ---- Helper to handle ObjectId safely ----

class PyObjectId(ObjectId):
    @classmethod
    def __get_pydantic_core_schema__(cls, _source_type, _handler):
        from pydantic_core import core_schema
        return core_schema.no_info_after_validator_function(
            cls.validate,
            core_schema.str_schema()
        )

    @classmethod
    def validate(cls, v, _info=None):
        if isinstance(v, ObjectId):
            return v
        try:
            return ObjectId(v)
        except Exception:
            raise ValueError(f"Invalid ObjectId: {v}")

    @classmethod
    def __get_pydantic_json_schema__(cls, schema, _handler):
        schema.update(type="string")
        return schema



# ---- Submodel for each recommended job ----
class RecommendedJobItem(BaseModel):
    jobId: str = Field(..., description="Unique identifier for the job")
    title: str = Field(..., description="Job title")
    role: str = Field(..., description="Job role or specialization")
    companyName: str = Field(..., description="Name of the company offering the job")
    companyLogo: str = Field(..., description="URL to the company's logo image")
    workMode: str = Field(..., description="Work mode of the job (e.g., remote, onsite)")
    aiSummary: Optional[str] = Field(default="", description="AI-generated job summary")
    createdAt: Optional[datetime] = Field(default_factory=datetime.utcnow, description="Job recommendation creation timestamp")
    updatedAt: Optional[datetime] = Field(default_factory=datetime.utcnow, description="Job recommendation update timestamp")


# ---- Main model for Recommended Jobs ----
class RecommendedJobs(BaseModel):
    id: Optional[PyObjectId] = Field(default=None, alias="_id")
    candidateId: str
    recommendedJobs: List[RecommendedJobItem] = Field(default_factory=list, description="List of recommended job entries")
    createdAt: Optional[datetime] = Field(default_factory=datetime.utcnow, description="Document creation timestamp")
    updatedAt: Optional[datetime] = Field(default_factory=datetime.utcnow, description="Document update timestamp")

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str}
    )
