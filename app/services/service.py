from datetime import datetime
from app.models.invoice import Invoice
from sqlalchemy.ext.asyncio import AsyncSession
from app.schemas.service import InvoiceMetadata


async def save_invoice_to_db(
    file_id: int, 
    building_id: int, 
    user_id: int, 
    metadata: InvoiceMetadata, 
    db: AsyncSession
):
    def to_date(d):
        if not d:
            return None
        try:
            return datetime.strptime(d, "%Y-%m-%d").date()
        except:
            return None

    invoice = Invoice(
        building_id=building_id,
        user_id=user_id,
        file_id=file_id,

        vendor=metadata.vendor,
        invoice_number=metadata.invoice_number,
        amount=metadata.amount,

        date=to_date(metadata.date),
        due_date=to_date(metadata.due_date),

        status=metadata.status or "unpaid",
    )

    db.add(invoice)
    await db.commit()
    await db.refresh(invoice)
