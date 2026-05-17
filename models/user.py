from pydantic import BaseModel, Field, ConfigDict, EmailStr, model_validator
from typing import Optional, Literal, Annotated
from datetime import datetime
from bson import ObjectId

# Reusable Type for ObjectId
PyObjectId = Annotated[
    str | ObjectId, 
    Field(default=None, alias="_id"),
]

class User(BaseModel):
    id: Optional[PyObjectId] = Field(default=None, alias="_id")
    email: EmailStr
    username: str
    password: Optional[str] = Field(default=None, min_length=8)
    authProvider: Literal["local", "google", "linkedin"] = Field(default="local")
    providerId: Optional[str] = None
    
    # Password Reset Logic
    resetPasswordOtp: Optional[str] = None
    resetPasswordOtpExpires: Optional[datetime] = None
    
    # Verification Logic
    isVerified: bool = Field(default=False)
    verificationToken: Optional[str] = None
    verificationTokenExpires: Optional[datetime] = None
    
    # RBAC & Auth
    role: Literal["admin", "candidate", "company"] = Field(default="candidate")
    refreshToken: Optional[str] = None
    
    # Timestamps (Mongoose handles these automatically, but we define them for the model)
    createdAt: Optional[datetime] = None
    updatedAt: Optional[datetime] = None

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str},
    )

    @model_validator(mode="after")
    def validate_password_requirement(self) -> "User":
        """
        Mimics the Mongoose 'required' function logic: 
        If provider is 'local', password must be present.
        """
        if self.authProvider == "local" and not self.password:
            raise ValueError("Password is required for local authentication.")
        return self

    def is_password_correct(self, password: str) -> bool:
        # In Python, you would typically use passlib or bcrypt here
        # Logic to check hash(password) == self.password
        pass

    def generate_access_token(self) -> str:
        # Logic for JWT generation
        pass