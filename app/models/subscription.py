from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Enum as SQLEnum, func
from sqlalchemy.orm import relationship
from app.core.database import Base
from datetime import datetime
from enum import Enum

class SubscriptionStatus(Enum):
    TRIAL = "trial"
    ACTIVE = "active"
    PENDING = "pending"
    PAST_DUE = "past_due"
    CANCELED = "canceled"
    EXPIRED = "expired"

class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    customer_id = Column(String, nullable=True)
    subscription_id = Column(String, nullable=True, index=True)
    description = Column(String, nullable=True)
    status = Column(SQLEnum(SubscriptionStatus), default=SubscriptionStatus.TRIAL)
    trial_start = Column(DateTime, default=datetime.utcnow)
    next_billing_date = Column(DateTime, nullable=True)
    plan_type = Column(String, nullable=False, default="professional")
    payment_provider = Column(String, default="stripe")
    canceled_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, onupdate=func.now())

    user = relationship("User", back_populates="subscription", uselist=False)


class ProcessedWebhook(Base):
    __tablename__ = "processed_webhooks"
    
    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(String, nullable=False, unique=True, index=True)
    received_at = Column(DateTime, nullable=False, server_default=func.now())


class SubscriptionHistory(Base):
    __tablename__ = "subscription_history"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    subscription_id = Column(String, nullable=True, index=True)
    customer_id = Column(String, nullable=True)
    status = Column(SQLEnum(SubscriptionStatus), nullable=False)
    plan_type = Column(String, nullable=False)
    trial_start = Column(DateTime, nullable=True)
    next_billing_date = Column(DateTime, nullable=True)
    canceled_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    description = Column(String, nullable=True)

    user = relationship("User", back_populates="subscription_history")