from app.services.payments.base import PaymentProvider
from app.services.payments.stripe_gateway import StripeProvider


def get_payment_provider() -> PaymentProvider:
    return StripeProvider()