from sqlalchemy import Column, Integer, String, Date, Numeric, ForeignKey, DateTime, func
from app.core.database import Base


class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(Integer, primary_key=True)
    building_id = Column(Integer, ForeignKey("buildings.id", ondelete="CASCADE"))
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    file_id = Column(Integer, ForeignKey("files.id", ondelete="CASCADE"))

    vendor = Column(String, nullable=True)
    invoice_number = Column(String, nullable=True)
    amount = Column(Numeric(12, 2))
    date = Column(Date)
    due_date = Column(Date)
    status = Column(String, default="unpaid")

    created_at = Column(DateTime, server_default=func.now())
