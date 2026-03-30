from datetime import datetime
from typing import Optional
from fastapi import HTTPException
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from app.models.subscription import Subscription, SubscriptionStatus, ProcessedWebhook
from app.models.user import User
from app.services.auth.email import send_email
from app.core.config import get_settings
from app.services.payments.base import PaymentProvider
from app.services.payments.history import add_subscription_history
from app.utils.helpers import run_stripe
import logging
import stripe

settings = get_settings()
logger = logging.getLogger(__name__)
stripe.api_key = settings.STRIPE_SECRET_KEY


class StripeProvider(PaymentProvider):
    async def create_customer(self, user: User) -> str:
        try:
            customer = await run_stripe(stripe.Customer.create, email=user.email)
            return customer.id
        except Exception:
            logger.exception("Stripe create_customer failed")
            raise HTTPException(status_code=502, detail="Failed to create Stripe customer")

    async def _map_stripe_status(self, status: str) -> SubscriptionStatus:
        mapping = {
            "active": SubscriptionStatus.ACTIVE,
            "trialing": SubscriptionStatus.TRIAL,
            "past_due": SubscriptionStatus.PAST_DUE,
            "incomplete": SubscriptionStatus.PENDING,
            "incomplete_expired": SubscriptionStatus.EXPIRED,
            "unpaid": SubscriptionStatus.EXPIRED,
            "canceled": SubscriptionStatus.CANCELED,
        }
        return mapping.get(status, SubscriptionStatus.EXPIRED)

    async def create_subscription(self, *, user: User, plan_type: str, payment_method_id: Optional[str], trial_days: Optional[int], db: AsyncSession) -> Subscription:
        existing = await db.execute(select(Subscription).filter(Subscription.user_id == user.id))
        subscription = existing.scalars().first()
        if subscription and subscription.status in (SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIAL):
            raise HTTPException(status_code=400, detail="User already has an active or trial subscription")

        if subscription and subscription.customer_id:
            customer_id = subscription.customer_id
        else:
            customer_id = await self.create_customer(user)

        if payment_method_id:
            try:
                await run_stripe(stripe.PaymentMethod.attach, payment_method_id, customer=customer_id)
                await run_stripe(stripe.Customer.modify, customer_id, invoice_settings={"default_payment_method": payment_method_id})
            except Exception:
                logger.exception("Failed to attach payment method")
                raise HTTPException(status_code=502, detail="Failed to attach payment method")

        create_args = {
            "customer": customer_id,
            "items": [{"price": settings.STRIPE_PRICE_ID}],
            "expand": ["latest_invoice.payment_intent", "pending_setup_intent"],
        }
        
        if trial_days and trial_days > 0:
            create_args["trial_period_days"] = trial_days

        try:
            sub = await run_stripe(stripe.Subscription.create, **create_args)
        except Exception:
            logger.exception("Stripe subscription creation failed")
            raise HTTPException(status_code=502, detail="Failed to create Stripe subscription")

        stripe_status = await self._map_stripe_status(getattr(sub, "status", ""))
        next_billing_date = datetime.fromtimestamp(int(getattr(sub, "current_period_end", 0))) if getattr(sub, "current_period_end", None) else None
        trial_start = datetime.fromtimestamp(int(getattr(sub, "trial_start", 0))) if getattr(sub, "trial_start", None) else None

        try:
            if subscription:
                subscription.customer_id = customer_id
                subscription.subscription_id = sub.id
                subscription.status = stripe_status
                subscription.description = "Subscription RENEWED"
                subscription.next_billing_date = next_billing_date
                subscription.plan_type = plan_type
                subscription.trial_start = trial_start
                subscription.canceled_at = None
            else:
                subscription = Subscription(
                    user_id=user.id,
                    customer_id=customer_id,
                    subscription_id=sub.id,
                    status=stripe_status,
                    description="Subscription CREATED",
                    trial_start=trial_start,
                    next_billing_date=next_billing_date,
                    plan_type=plan_type,
                    payment_provider="stripe",
                )
                db.add(subscription)

            await db.commit()
            await db.refresh(subscription)
            return subscription

        except Exception:
            await db.rollback()
            logger.exception("Failed to save subscription in DB")
            raise HTTPException(status_code=500, detail="Subscription creation failed")

    async def cancel_subscription(self, subscription_id: str, db: AsyncSession) -> str:
        if not subscription_id:
            raise HTTPException(status_code=400, detail="Missing subscription id to cancel")
        try:
            invoices = await run_stripe(stripe.Invoice.list, subscription=subscription_id, limit=1)

            invoice = invoices.data[0] if invoices.data else None
            refund_status = "no_refund"

            if invoice and invoice.status == "paid":
                paid_at = invoice.status_transitions.get("paid_at")

                if paid_at:
                    paid_at_dt = datetime.utcfromtimestamp(paid_at)
                    days_since_payment = (datetime.utcnow() - paid_at_dt).days

                    if days_since_payment <= 7:
                        try:
                            await run_stripe(stripe.Refund.create, payment_intent=invoice.payment_intent)
                            refund_status = "refunded"
                        except Exception:
                            logger.exception("Failed to issue refund for subscription")
                            raise HTTPException(status_code=502, detail="Failed to issue refund")

            await run_stripe(stripe.Subscription.delete, subscription_id)
            result = await db.execute(select(Subscription).filter(Subscription.subscription_id == subscription_id))
            current = result.scalars().first()
            if current:
                current.status = SubscriptionStatus.CANCELED
                current.description = "Subscription CANCELED"
                current.canceled_at = datetime.utcnow()
                await db.commit()
                
            logger.info(f"Subscription {subscription_id} canceled with refund status: {refund_status}")
            return refund_status

        except HTTPException:
            raise
        except Exception:
            logger.exception("Failed to cancel stripe subscription")
            await db.rollback()
            raise HTTPException(status_code=502, detail="Failed to cancel subscription on Stripe")

    async def handle_webhook(self, payload: str, signature: str, db: AsyncSession) -> None:
        try:
            event = await run_stripe(stripe.Webhook.construct_event, payload, signature, settings.STRIPE_WEBHOOK_SECRET)
        except stripe.error.SignatureVerificationError:
            logger.warning("Invalid Stripe webhook signature")
            raise HTTPException(status_code=400, detail="Invalid webhook signature")
        except Exception:
            logger.exception("Failed to construct Stripe webhook event")
            raise HTTPException(status_code=400, detail="Failed to parse webhook event")

        event_id = event.get("id")
        event_type = event["type"]
        data = event.get("data", {}).get("object", {}) or {}

        if event_id:
            result = await db.execute(select(ProcessedWebhook).filter(ProcessedWebhook.event_id == event_id))
            exists = result.scalars().first()
            if exists:
                logger.info(f"Webhook already processed: {event_id}")
                return
            db.add(ProcessedWebhook(event_id=event_id))
            await db.commit()

        try:
            if event_type == "customer.subscription.trial_will_end":
                sub_id = data.get("id")

                result = await db.execute(select(Subscription).options(selectinload(Subscription.user)).filter(Subscription.subscription_id == sub_id))
                subscription = result.scalars().first()
                
                if subscription and subscription.user:
                    subscription.description = "Trial Ending Soon"
                    await db.commit()
                    await send_email(
                        to=subscription.user.email,
                        subject="APT Portfolio Pulse: Your trial is ending soon",
                        body="Your trial period is ending soon. Ensure your payment method is valid to continue uninterrupted.",
                    )

            elif event_type == "invoice.payment_succeeded":
                sub_id = data.get("subscription")
                result = await db.execute(select(Subscription).filter(Subscription.subscription_id == sub_id))
                subscription = result.scalars().first()
                if subscription:
                    subscription.plan_type = "professional"
                    lines = data.get("lines", {}).get("data", [])
                    if lines and "period" in lines[0]:
                        next_billing = datetime.fromtimestamp(int(lines[0]["period"]["end"]))
                    elif data.get("period_end"):
                        next_billing = datetime.fromtimestamp(int(data["period_end"]))
                    subscription.status = SubscriptionStatus.ACTIVE
                    subscription.description = "Invoice Paid"
                    subscription.next_billing_date = next_billing
                    subscription.canceled_at = None
                    await db.commit()
                    
                    await add_subscription_history(
                        db=db,
                        user_id=subscription.user_id,
                        subscription_id=subscription.subscription_id,
                        customer_id=subscription.customer_id,
                        status=SubscriptionStatus.ACTIVE,
                        plan_type="professional",
                        trial_start=subscription.trial_start,
                        next_billing_date=next_billing,
                        canceled_at=subscription.canceled_at,
                        description="Invoice Paid",
                    )

            elif event_type == "invoice.payment_failed":
                sub_id = data.get("subscription")
                result = await db.execute(select(Subscription).options(selectinload(Subscription.user)).filter(Subscription.subscription_id == sub_id))
                subscription = result.scalars().first()

                attempt_count = data.get("attempt_count", 0)
                if subscription and subscription.user:
                    subscription.status = SubscriptionStatus.PAST_DUE
                    subscription.description = "Payment Failed"
                    await db.commit()
                    await send_email(
                        to=subscription.user.email,
                        subject="APT Portfolio Pulse: Payment failed",
                        body=f"Your payment attempt {attempt_count} failed. Please renew your subscription.",
                    )
                
                    await add_subscription_history(
                        db=db,
                        user_id=subscription.user_id,
                        subscription_id=subscription.subscription_id,
                        customer_id=subscription.customer_id,
                        status=SubscriptionStatus.PAST_DUE,
                        plan_type=subscription.plan_type,
                        trial_start=subscription.trial_start,
                        next_billing_date=subscription.next_billing_date,
                        canceled_at=subscription.canceled_at,
                        description="Payment Failed",
                    )
                    
            elif event_type == "charge.refunded":
                amount = data.get("amount_refunded")
                charge_id = data.get("id")

                invoice_list = await run_stripe(stripe.Invoice.list, charge=charge_id, limit=1)
                invoice = invoice_list.data[0] if invoice_list.data else None

                if invoice and invoice.subscription:
                    sub_id = invoice.subscription
                    result = await db.execute(select(Subscription).filter(Subscription.subscription_id == sub_id))
                    subscription = result.scalars().first()

                    if subscription:
                        amount_usd = amount / 100 if amount is not None else 0
                        subscription.description = f"Refund Issued: {amount_usd} USD"
                        await db.commit()
                        
                        await add_subscription_history(
                            db=db,
                            user_id=subscription.user_id,
                            subscription_id=sub_id,
                            customer_id=subscription.customer_id,
                            status=subscription.status,
                            plan_type=subscription.plan_type,
                            trial_start=subscription.trial_start,
                            next_billing_date=subscription.next_billing_date,
                            canceled_at=subscription.canceled_at,
                            description=f"Refund Issued: {amount_usd} USD",
                        )

            elif event_type in ("customer.subscription.created", "customer.subscription.deleted", "customer.subscription.updated"):
                sub_id = data.get("id")
                result = await db.execute(select(Subscription).filter(Subscription.subscription_id == sub_id))
                subscription = result.scalars().first()
                if subscription:
                    stripe_status = data.get("status")
                    subscription.status = await self._map_stripe_status(stripe_status)
                    description = f"Subscription {event_type.replace('customer.subscription.', '').capitalize()}"

                    if stripe_status == "trialing" and data.get("trial_end"):
                        subscription.next_billing_date = datetime.fromtimestamp(int(data["trial_end"]))
                    elif data.get("current_period_end"):
                        subscription.next_billing_date = datetime.fromtimestamp(int(data["current_period_end"]))

                    if stripe_status == "canceled" and data.get("canceled_at"):
                        subscription.canceled_at = datetime.fromtimestamp(int(data["canceled_at"]))

                    subscription.description = description
                    await db.commit()

                    await add_subscription_history(
                        db=db,
                        user_id=subscription.user_id,
                        subscription_id=subscription.subscription_id,
                        customer_id=subscription.customer_id,
                        status=subscription.status,
                        plan_type=subscription.plan_type,
                        trial_start=subscription.trial_start,
                        next_billing_date=subscription.next_billing_date,
                        canceled_at=subscription.canceled_at,
                        description=description,
                    )
            else:
                logger.debug(f"Unhandled Stripe event: {event_type}")

        except Exception as e:
            logger.exception(f"Failed processing webhook {event_type}: {str(e)}")
            await db.rollback()
            raise
