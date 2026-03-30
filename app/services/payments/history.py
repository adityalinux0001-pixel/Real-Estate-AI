from sqlalchemy.ext.asyncio import AsyncSession
from app.models.subscription import SubscriptionHistory, SubscriptionStatus
from sqlalchemy.future import select
from datetime import datetime


async def add_subscription_history(
    db: AsyncSession,
    user_id: int,
    subscription_id: str,
    customer_id: str,
    status: SubscriptionStatus,
    plan_type: str,
    trial_start: datetime | None = None,
    next_billing_date: datetime | None = None,
    canceled_at: datetime | None = None,
    description: str | None = None,
):
    history = SubscriptionHistory(
        user_id=user_id,
        subscription_id=subscription_id,
        customer_id=customer_id,
        status=status,
        plan_type=plan_type,
        trial_start=trial_start,
        next_billing_date=next_billing_date,
        canceled_at=canceled_at,
        description=description,
    )
    db.add(history)
    await db.commit()
    

async def fetch_billing_history(user, db: AsyncSession):
    result = await db.execute(
        select(SubscriptionHistory).where(SubscriptionHistory.user_id == user.id).order_by(SubscriptionHistory.created_at.desc())
    )
    history_records = result.scalars().all()
    return history_records
