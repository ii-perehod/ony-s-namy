"""Stripe payment integration for photo packs and monthly subscriptions."""

import stripe
from config import settings

stripe.api_key = settings.STRIPE_SECRET_KEY

# ── One-time photo packs ─────────────────────────────────────────────

PHOTO_PACKS = {
    "pack_10": {"count": 10, "label": "10 фото"},
    "pack_50": {"count": 50, "label": "50 фото"},
    "pack_200": {"count": 200, "label": "200 фото"},
}

# ── Monthly subscription plans ───────────────────────────────────────

SUBSCRIPTION_PLANS = {
    "sub_30": {
        "photo_limit": 30,
        "label": "30 фото/мес",
        "price_id_setting": "STRIPE_SUB_PRICE_30",
    },
    "sub_100": {
        "photo_limit": 100,
        "label": "100 фото/мес",
        "price_id_setting": "STRIPE_SUB_PRICE_100",
    },
    "sub_unlimited": {
        "photo_limit": 0,  # 0 = unlimited
        "label": "Безлимит",
        "price_id_setting": "STRIPE_SUB_PRICE_UNLIMITED",
    },
}


def _get_sub_price_id(plan_id: str) -> str:
    """Resolve Stripe price ID for a subscription plan."""
    plan = SUBSCRIPTION_PLANS.get(plan_id)
    if not plan:
        raise ValueError(f"Неизвестный план подписки: {plan_id}")
    setting_name = plan["price_id_setting"]
    price_id = getattr(settings, setting_name, "")
    if not price_id:
        raise ValueError(
            f"Не настроен Stripe Price ID для плана {plan_id}. "
            f"Добавьте {setting_name} в .env"
        )
    return price_id


# ── Checkout sessions ────────────────────────────────────────────────

def create_checkout_session(session_id: str, pack_id: str, success_url: str, cancel_url: str) -> str:
    """Create a Stripe Checkout session for a one-time pack and return the URL."""
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
            "type": "pack",
        },
    )
    return checkout.url


def create_subscription_checkout(
    session_id: str, plan_id: str, success_url: str, cancel_url: str
) -> str:
    """Create a Stripe Checkout session for a monthly subscription."""
    plan = SUBSCRIPTION_PLANS.get(plan_id)
    if not plan:
        raise ValueError(f"Неизвестный план подписки: {plan_id}")

    price_id = _get_sub_price_id(plan_id)

    checkout = stripe.checkout.Session.create(
        payment_method_types=["card"],
        line_items=[{
            "price": price_id,
            "quantity": 1,
        }],
        mode="subscription",
        success_url=success_url + f"?session_id={session_id}&plan={plan_id}",
        cancel_url=cancel_url,
        metadata={
            "app_session_id": session_id,
            "plan_id": plan_id,
            "photo_limit": str(plan["photo_limit"]),
            "type": "subscription",
        },
        subscription_data={
            "metadata": {
                "app_session_id": session_id,
                "plan_id": plan_id,
                "photo_limit": str(plan["photo_limit"]),
            },
        },
    )
    return checkout.url


# ── Webhook handling ─────────────────────────────────────────────────

def handle_webhook(payload: bytes, sig_header: str) -> dict | None:
    """Verify and process Stripe webhook. Returns event info dict."""
    event = stripe.Webhook.construct_event(
        payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
    )

    event_type = event["type"]
    obj = event["data"]["object"]

    # One-time pack purchase completed
    if event_type == "checkout.session.completed":
        metadata = obj.get("metadata", {})
        if metadata.get("type") == "subscription":
            # Subscription activated via checkout — handled by invoice.paid
            return {
                "event": "subscription_created",
                "app_session_id": metadata.get("app_session_id"),
                "plan_id": metadata.get("plan_id"),
                "photo_limit": metadata.get("photo_limit"),
                "stripe_subscription_id": obj.get("subscription"),
            }
        # One-time pack
        return {
            "event": "pack_purchased",
            "app_session_id": metadata.get("app_session_id"),
            "photo_count": metadata.get("photo_count"),
        }

    # Subscription invoice paid (initial + renewals)
    if event_type == "invoice.paid":
        sub_id = obj.get("subscription")
        if sub_id:
            # Fetch subscription to get metadata
            sub = stripe.Subscription.retrieve(sub_id)
            metadata = sub.get("metadata", {})
            return {
                "event": "subscription_renewed",
                "app_session_id": metadata.get("app_session_id"),
                "plan_id": metadata.get("plan_id"),
                "photo_limit": metadata.get("photo_limit"),
                "stripe_subscription_id": sub_id,
            }

    # Subscription cancelled or expired
    if event_type in ("customer.subscription.deleted", "customer.subscription.updated"):
        metadata = obj.get("metadata", {})
        status = obj.get("status")
        if status in ("canceled", "unpaid", "past_due"):
            return {
                "event": "subscription_cancelled",
                "app_session_id": metadata.get("app_session_id"),
                "stripe_subscription_id": obj.get("id"),
            }

    return None
