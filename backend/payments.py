"""Stripe payment integration for buying additional photo packs."""

import stripe
from config import settings

stripe.api_key = settings.STRIPE_SECRET_KEY

# Photo packs available for purchase
PHOTO_PACKS = {
    "pack_10": {"count": 10, "label": "10 фото"},
    "pack_50": {"count": 50, "label": "50 фото"},
    "pack_200": {"count": 200, "label": "200 фото"},
}


def create_checkout_session(session_id: str, pack_id: str, success_url: str, cancel_url: str) -> str:
    """Create a Stripe Checkout session and return the URL."""
    pack = PHOTO_PACKS.get(pack_id)
    if not pack:
        raise ValueError(f"Unknown pack: {pack_id}")

    checkout = stripe.checkout.Session.create(
        payment_method_types=["card"],
        line_items=[{
            "price": settings.STRIPE_PRICE_ID,
            "quantity": pack["count"],
        }],
        mode="payment",
        success_url=success_url + f"?session_id={session_id}&pack={pack_id}",
        cancel_url=cancel_url,
        metadata={
            "app_session_id": session_id,
            "pack_id": pack_id,
            "photo_count": str(pack["count"]),
        },
    )
    return checkout.url


def handle_webhook(payload: bytes, sig_header: str) -> dict | None:
    """Verify and process Stripe webhook. Returns metadata on success."""
    event = stripe.Webhook.construct_event(
        payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
    )

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        return session.get("metadata")

    return None
