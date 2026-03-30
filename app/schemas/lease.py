from pydantic import BaseModel
from typing import Optional
from datetime import date


class LeaseInput(BaseModel):
    tenant_name: Optional[str] = None
    property_address: Optional[str] = None
    rent_start_date: Optional[date] = None
    rent_end_date: Optional[date] = None
    monthly_rent: Optional[float] = None
    security_deposit: Optional[float] = None
    guarantor_name: Optional[str] = None
    late_fee: Optional[float] = None
    payment_due_date: Optional[str] = None
    additional_notes: Optional[str] = None
