from typing import List, Optional, Any
from pydantic import BaseModel, Field, EmailStr, field_validator
from bson import ObjectId
from datetime import datetime
from pydantic_core import core_schema

# ---------------------------
# Helper for MongoDB ObjectId
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
# Main Company Model
# ---------------------------
class CompanyModel(BaseModel):
    model_config = {
        "arbitrary_types_allowed": True,
        "json_encoders": {
            ObjectId: str,
            datetime: lambda dt: dt.isoformat() if dt else None
        }
    }

    id: Optional[PyObjectId] = Field(default=None, alias="_id")
    userId: PyObjectId
    companyName: Optional[str] = None
    logoUrl: Optional[str] = None
    website: Optional[str] = None
    linkedInUrl: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    foundedYear: Optional[int] = None
    description: Optional[str] = None
    techStack: List[str] = Field(default_factory=list)
    contactEmail: Optional[EmailStr] = None
    isVerified: bool = False
    hiringStatus: Optional[str] = Field(default="actively_hiring", pattern="^(actively_hiring|paused|not_hiring)$")
    ntnNumber: Optional[str] = None
    isDeleted: Optional[bool] = False
    createdAt: Optional[datetime] = None
    updatedAt: Optional[datetime] = None

    # ---------------------------
    # Validators
    # ---------------------------
    @field_validator('techStack', mode='before')
    @classmethod
    def normalize_techstack(cls, v):
        if not v:
            return []
        if isinstance(v, list):
            return [str(item).lower() for item in v]
        return []

    @field_validator('foundedYear')
    @classmethod
    def validate_founded_year(cls, v):
        if v is not None:
            current_year = datetime.now().year
            if v < 1900 or v > current_year:
                raise ValueError(f"Founded year must be between 1900 and {current_year}")
        return v
