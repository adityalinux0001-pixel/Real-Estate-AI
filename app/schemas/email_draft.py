from pydantic import BaseModel
from typing import Dict, Any

# Schemas Email Template 
class TenantBase(BaseModel):
    name: str
    data: Dict[str, Any]

class TenantCreate(TenantBase):
    pass

class TenantRead(TenantBase):
    id: int

    class Config:
        from_attributes = True

class EmailTemplateBase(BaseModel):
    title: str
    content: str

class EmailTemplateCreate(EmailTemplateBase):
    pass

class EmailTemplateRead(EmailTemplateBase):
    id: int
    user_id: int

    class Config:
        from_attributes = True



# Schemas for Tenant
class TenantBase(BaseModel):
    name: str
    data: Dict[str, Any]

class TenantCreate(TenantBase):
    pass

class TenantRead(TenantBase):
    id: int
    user_id: int

    class Config:
        from_attributes = True
