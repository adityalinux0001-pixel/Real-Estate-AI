from pydantic import BaseModel, EmailStr
from typing import Optional, Literal
from app.schemas.subscription import SubscriptionResponse

class UserBase(BaseModel):
    company_name: str
    contact_person: Optional[str] = None
    company_address: str
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: str
    email: EmailStr
    phone_number: Optional[str] = None

class UserCreate(UserBase):
    password: str
    
class SuperAdminCreate(BaseModel):
    email: EmailStr
    password: str
    contact_person: str
    company_name: Optional[str] = None   
    is_superadmin: bool = True

class UserUpdate(BaseModel):
    company_name: Optional[str] = None
    contact_person: Optional[str] = None
    company_address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    phone_number: Optional[str] = None
    banner_photo: Optional[str] = None
    photo: Optional[str] = None

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class UserResponse(UserBase):
    id: int
    banner_photo: Optional[str] = None
    photo: Optional[str] = None
    is_active: bool
    is_verified: bool
    is_superadmin: bool
    subscription: Optional[SubscriptionResponse] = None

    class Config:
        from_attributes = True

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class VerifyOtpRequest(BaseModel):
    email: EmailStr
    otp: str
    type: Literal["verification", "reset"]

class ResetPasswordRequest(BaseModel):
    email: EmailStr
    new_password: str
    
