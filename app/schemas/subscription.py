from pydantic import BaseModel
from datetime import datetime
from typing import Optional, Literal
from app.models.subscription import SubscriptionStatus


class SubscriptionCreate(BaseModel):
    plan_type: Literal["trial", "professional"] = "trial"
    payment_method_id: Optional[str] = None

class SubscriptionResponse(BaseModel):
    id: int
    user_id: int
    customer_id: Optional[str]
    subscription_id: Optional[str]
    status: SubscriptionStatus
    description: Optional[str]
    trial_start: Optional[datetime]
    next_billing_date: Optional[datetime]
    plan_type: str
    payment_provider: str
    canceled_at: Optional[datetime]
    created_at: Optional[datetime]
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True
        
class SubscriptionHistoryResponse(BaseModel):
    id: int
    user_id: int
    subscription_id: Optional[str]
    customer_id: Optional[str]
    status: SubscriptionStatus
    plan_type: str
    trial_start: Optional[datetime]
    next_billing_date: Optional[datetime]
    canceled_at: Optional[datetime]
    created_at: Optional[datetime]
    description: Optional[str]

    class Config:
        from_attributes = True
