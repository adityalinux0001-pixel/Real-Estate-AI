from abc import ABC, abstractmethod
from typing import Optional
from app.models.user import User
from app.models.subscription import Subscription
from sqlmodel.ext.asyncio.session import AsyncSession

class PaymentProvider(ABC):
    @abstractmethod
    async def create_customer(self, user: User) -> str:
        """Create a customer and return provider-specific ID."""
        pass

    @abstractmethod
    async def create_subscription(self, user: User, plan_type: str, payment_method_id: Optional[str], trial_days: int, db: AsyncSession) -> Subscription:
        """Setup subscription with trial period and persist in DB."""
        pass

    @abstractmethod
    async def cancel_subscription(self, subscription_id: str, db: AsyncSession) -> str:
        """Cancel the subscription on provider."""
        pass

    @abstractmethod
    async def handle_webhook(self, payload: str, signature: str, db: AsyncSession) -> None:
        """Handle incoming webhooks from the provider."""
        pass