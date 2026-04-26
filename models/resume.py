from typing import List, Optional, Union, Any
from pydantic import BaseModel, Field, field_validator
from pydantic_core import core_schema
from bson import ObjectId
from datetime import datetime

# ---------------------------
# Helper to handle ObjectId
# ---------------------------
from typing import Any
from bson import ObjectId
from pydantic_core import core_schema

class PyObjectId(ObjectId):
    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: Any, handler
    ) -> core_schema.CoreSchema:
        return core_schema.union_schema([
            # 1. Check if it's already an ObjectId instance
            core_schema.is_instance_schema(ObjectId),
            # 2. Use a chain: first ensure it's a string, then run your validator
            core_schema.chain_schema([
                core_schema.str_schema(),
                core_schema.no_info_plain_validator_function(cls.validate),
            ]),
        ])

    @classmethod
    def validate(cls, v: Any) -> ObjectId:
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid ObjectId")
        return ObjectId(v)



# ---------------------------
# Nested Models
# ---------------------------

class ExperienceModel(BaseModel):
    unique_id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    company: Optional[str] = None
    position: Optional[str] = None
    startDate: Optional[str] = None
    endDate: Optional[str] = None
    description: Optional[str] = None

class EducationModel(BaseModel):
    unique_id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    institution: Optional[str] = None
    degree: Optional[str] = None
    startYear: Optional[int] = None
    endYear: Optional[int] = None

class ProjectModel(BaseModel):
    unique_id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    name: Optional[str] = None
    description: Optional[str] = None
    link: Optional[str] = None
    technologies: List[str] = Field(default_factory=list)

class CertificationModel(BaseModel):
    unique_id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    name: Optional[str] = None
    issuer: Optional[str] = None
    year: Optional[int] = None

# ---------------------------
# Parsed Data
# ---------------------------

class ParsedDataModel(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    linkedin: Optional[str] = None
    github: Optional[str] = None
    portfolio: Optional[str] = None
    summary: Optional[str] = None
    skills: List[str] = Field(default_factory=list)
    experience: List[ExperienceModel] = Field(default_factory=list)
    education: List[EducationModel] = Field(default_factory=list)
    projects: List[ProjectModel] = Field(default_factory=list)
    certifications: List[CertificationModel] = Field(default_factory=list)

    @field_validator('skills', 'experience', 'education', 'projects', 'certifications', mode='before')
    @classmethod
    def validate_lists(cls, v):
        if v is None:
            return []
        if isinstance(v, list):
            return v
        return []

# ---------------------------
# Main Resume Model
# ---------------------------

class ResumeModel(BaseModel):
    model_config = {
        "arbitrary_types_allowed": True,
        "json_encoders": {
            ObjectId: str,
            datetime: lambda dt: dt.isoformat() if dt else None
        }
    }
    
    # id: Optional[PyObjectId] = Field(default=None, alias="_id")
    candidateId: PyObjectId
    fileUrl: Optional[str] = None
    parsedData: ParsedDataModel = Field(default_factory=ParsedDataModel)
    aiScore: Optional[float] = None
    aiSuggestions: List[str] = Field(default_factory=list)
    createdAt: Optional[datetime] = None
    updatedAt: Optional[datetime] = None

    @field_validator('aiSuggestions', mode='before')
    @classmethod
    def validate_ai_suggestions(cls, v):
        if v is None:
            return []
        if isinstance(v, list):
            return v
        return []