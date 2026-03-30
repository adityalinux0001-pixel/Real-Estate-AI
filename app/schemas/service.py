from pydantic import BaseModel, validator
from typing import Optional
from datetime import datetime


class InvoiceMetadata(BaseModel):
    vendor: Optional[str] = None
    invoice_number: Optional[str] = None
    amount: Optional[float] = None
    date: Optional[str] = None
    due_date: Optional[str] = None
    status: Optional[str] = "unpaid"

    @validator("amount", pre=True)
    def validate_amount(cls, v):
        if v is None or v == "":
            return None
        try:
            return float(v)
        except:
            return None

    @validator("date", "due_date", pre=True)
    def validate_dates(cls, v):
        if not v:
            return None
        try:
            d = datetime.fromisoformat(v.replace("/", "-"))
            return d.date().isoformat()
        except:
            return None


