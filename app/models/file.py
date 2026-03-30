from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from app.core.database import Base
from datetime import datetime

class File(Base):
    __tablename__ = "files"
    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String)
    path = Column(String)
    category = Column(String)
    building_id = Column(Integer, ForeignKey("buildings.id"), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    uploaded_at = Column(DateTime, default=datetime.utcnow)

    building = relationship("Building", back_populates="files")
    user = relationship("User", back_populates="files")
