from fastapi import APIRouter, Depends, HTTPException, Request, Header
from sqlmodel.ext.asyncio.session import AsyncSession
from app.core.database import get_db
from app.dependencies import get_current_user
from app.models.subscription import SubscriptionStatus
from app.schemas.subscription import SubscriptionCreate, SubscriptionHistoryResponse, SubscriptionResponse
from app.services.payments.helper import get_payment_provider
from app.services.auth.email import send_email
from app.core.config import get_settings
from app.services.payments.history import fetch_billing_history
import logging

router = APIRouter(prefix="/billing", tags=["billing"])
settings = get_settings()
logger = logging.getLogger(__name__)


@router.post("/setup", response_model=SubscriptionResponse)
async def setup_billing(request: SubscriptionCreate, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    subscription = current_user.subscription
    if subscription and subscription.status in (SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIAL):
        raise HTTPException(status_code=400, detail="Active subscription already exists")
    
    if subscription and subscription.status in (SubscriptionStatus.CANCELED, SubscriptionStatus.EXPIRED):
        raise HTTPException(status_code=400, detail="You have a canceled or expired subscription. Please renew your subscription.")

    provider = get_payment_provider()
    new_sub = await provider.create_subscription(
        user=current_user,
        plan_type="trial",
        payment_method_id=request.payment_method_id,
        trial_days=settings.TRIAL_DAYS,
        db=db,
    )
    return new_sub


@router.get("/status", response_model=SubscriptionResponse)
async def get_subscription_status(db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    subscription = current_user.subscription
    if not subscription:
        raise HTTPException(status_code=404, detail="No subscription found")
    return subscription


@router.get("/history", response_model=list[SubscriptionHistoryResponse])
async def get_billing_history(db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    return await fetch_billing_history(current_user, db)


@router.delete("/cancel")
async def cancel_subscription(db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    subscription = current_user.subscription
    if not subscription or not subscription.subscription_id:
        raise HTTPException(status_code=404, detail="No subscription found")

    provider = get_payment_provider()
    refund_status = await provider.cancel_subscription(subscription.subscription_id, db)

    await send_email(
        to=current_user.email,
        subject="APT Portfolio Pulse: Subscription canceled",
        body=f"Your subscription has been canceled, you can renew anytime. Refund status: {refund_status}",
    )
    return {"message": "Subscription canceled", "refund_status": refund_status}


@router.post("/renew")
async def renew_subscription(request: SubscriptionCreate, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    subscription = current_user.subscription
    
    if not subscription:
        raise HTTPException(status_code=400, detail="No subscription found to renew.")

    if subscription.status in [SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIAL]:
        raise HTTPException(status_code=400, detail="You already have an active subscription. No need to renew.")

    if subscription.status not in [SubscriptionStatus.CANCELED, SubscriptionStatus.EXPIRED]:
        raise HTTPException(status_code=400, detail="No canceled or expired subscription found to renew.")
    
    try:
        provider = get_payment_provider()
        new_sub = await provider.create_subscription(
            user=current_user,
            plan_type="professional",
            payment_method_id=request.payment_method_id,
            trial_days=None,  # No trial on renewals
            db=db,
        )

        return {"message": "Subscription renewed successfully", "subscription": new_sub}
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Error renewing subscription for user {current_user.id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to renew subscription")


@router.post("/webhook")
async def stripe_webhook(request: Request, sig_header: str = Header(..., alias="Stripe-Signature"), db: AsyncSession = Depends(get_db)):
    payload = await request.body()
    provider = get_payment_provider()
    await provider.handle_webhook(payload.decode("utf-8"), sig_header, db)
    
    return {"status": "success"}