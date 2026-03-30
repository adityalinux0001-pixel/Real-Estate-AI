from sqlalchemy import Column, DateTime, Integer, String, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    company_name = Column(String, unique=True, nullable=False)
    contact_person = Column(String, nullable=True)
    company_address = Column(String, nullable=False)
    city = Column(String, nullable=True)
    state = Column(String, nullable=True)
    zip_code = Column(String, nullable=False)
    phone_number = Column(String, nullable=True)
    email = Column(String, unique=True, nullable=False)
    banner_photo = Column(String, nullable=True)
    photo = Column(String, nullable=True)
    password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    is_superadmin = Column(Boolean, default=False)

    buildings = relationship("Building", back_populates="owner", cascade="all, delete-orphan")
    files = relationship("File", back_populates="user")
    subscription = relationship("Subscription", back_populates="user", uselist=False, cascade="all, delete-orphan")
    subscription_history = relationship("SubscriptionHistory", back_populates="user", order_by="SubscriptionHistory.created_at.desc()", cascade="all, delete-orphan")
    sessions = relationship("ChatSession", back_populates="user")
    otps = relationship("OTP", back_populates="user")
    
    email_templates = relationship("EmailTemplate", back_populates="user", cascade="all, delete-orphan")
    tenants = relationship("Tenant", back_populates="user", cascade="all, delete-orphan")
    tenant_keys = relationship("TenantKey", back_populates="user", cascade="all, delete-orphan")
    

class OTP(Base):
    __tablename__ = "otps"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    code = Column(String, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    type = Column(String, default="verification")
    verified = Column(Boolean, default=False)
    
    user = relationship("User", back_populates="otps")
