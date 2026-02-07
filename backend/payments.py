"""YooKassa payment integration for photo packs and monthly subscriptions.

Supports СБП, МИР, Visa/MC (российские карты), кошельки.
For subscriptions, the first payment saves the payment method (autopayment).
Recurring charges require a scheduler (cron) calling create_recurring_payment().
"""

from yookassa import Configuration, Payment
from config import settings

Configuration.account_id = settings.YOOKASSA_SHOP_ID
Configuration.secret_key = settings.YOOKASSA_SECRET_KEY

# ── One-time photo packs ─────────────────────────────────────────────

PHOTO_PACKS = {
    "pack_10": {"count": 10, "label": "10 фото", "price": "199.00"},
    "pack_50": {"count": 50, "label": "50 фото", "price": "799.00"},
    "pack_200": {"count": 200, "label": "200 фото", "price": "2499.00"},
}

# ── Monthly subscription plans ───────────────────────────────────────

SUBSCRIPTION_PLANS = {
    "sub_30": {
        "photo_limit": 30,
        "label": "30 фото/мес",
        "price": "299.00",
    },
    "sub_100": {
        "photo_limit": 100,
        "label": "100 фото/мес",
        "price": "699.00",
    },
    "sub_unlimited": {
        "photo_limit": 0,  # 0 = unlimited
        "label": "Безлимит",
        "price": "1499.00",
    },
}


# ── Checkout (one-time pack) ────────────────────────────────────────

def create_checkout_session(
    session_id: str, pack_id: str, success_url: str, cancel_url: str
) -> str:
    """Create a YooKassa payment for a one-time photo pack. Returns confirmation URL."""
    pack = PHOTO_PACKS.get(pack_id)
    if not pack:
        raise ValueError(f"Неизвестный пакет: {pack_id}")

    payment = Payment.create({
        "amount": {
            "value": pack["price"],
            "currency": "RUB",
        },
        "confirmation": {
            "type": "redirect",
            "return_url": success_url + f"?session_id={session_id}&pack={pack_id}",
        },
        "capture": True,
        "description": f"Пакет «{pack['label']}» — ФотоРеставратор",
        "metadata": {
            "app_session_id": session_id,
            "pack_id": pack_id,
            "photo_count": str(pack["count"]),
            "type": "pack",
        },
    })

    return payment.confirmation.confirmation_url


# ── Checkout (subscription — first payment) ─────────────────────────

def create_subscription_checkout(
    session_id: str, plan_id: str, success_url: str, cancel_url: str
) -> str:
    """Create a YooKassa payment that saves the payment method for autopayments."""
    plan = SUBSCRIPTION_PLANS.get(plan_id)
    if not plan:
        raise ValueError(f"Неизвестный план подписки: {plan_id}")

    payment = Payment.create({
        "amount": {
            "value": plan["price"],
            "currency": "RUB",
        },
        "confirmation": {
            "type": "redirect",
            "return_url": success_url + f"?session_id={session_id}&plan={plan_id}",
        },
        "capture": True,
        "save_payment_method": True,
        "description": f"Подписка «{plan['label']}» — ФотоРеставратор",
        "metadata": {
            "app_session_id": session_id,
            "plan_id": plan_id,
            "photo_limit": str(plan["photo_limit"]),
            "type": "subscription",
        },
    })

    return payment.confirmation.confirmation_url


# ── Recurring payment (called by scheduler for subscription renewal) ─

def create_recurring_payment(
    session_id: str, plan_id: str, payment_method_id: str
) -> str | None:
    """Charge a saved payment method for subscription renewal.
    Call this monthly from a cron job / scheduler.
    Returns payment ID on success, None on failure."""
    plan = SUBSCRIPTION_PLANS.get(plan_id)
    if not plan:
        return None

    payment = Payment.create({
        "amount": {
            "value": plan["price"],
            "currency": "RUB",
        },
        "payment_method_id": payment_method_id,
        "capture": True,
        "description": f"Продление подписки «{plan['label']}» — ФотоРеставратор",
        "metadata": {
            "app_session_id": session_id,
            "plan_id": plan_id,
            "photo_limit": str(plan["photo_limit"]),
            "type": "subscription_renewal",
        },
    })

    return payment.id


# ── Webhook handling ─────────────────────────────────────────────────

def handle_webhook(payload: dict) -> dict | None:
    """Process YooKassa webhook notification.

    Unlike Stripe, YooKassa doesn't use signature headers.
    We verify by fetching the payment from the API by ID.
    """
    event_type = payload.get("event")
    obj = payload.get("object", {})
    payment_id = obj.get("id")

    if not payment_id:
        return None

    # Verify payment by fetching it from YooKassa API
    payment = Payment.find_one(payment_id)
    if not payment:
        return None

    metadata = dict(payment.metadata) if payment.metadata else {}

    # ── Payment succeeded ──
    if event_type == "payment.succeeded" and payment.status == "succeeded":
        pay_type = metadata.get("type")

        if pay_type == "pack":
            return {
                "event": "pack_purchased",
                "app_session_id": metadata.get("app_session_id"),
                "photo_count": metadata.get("photo_count"),
            }

        if pay_type == "subscription":
            # First subscription payment — save payment method for recurring
            pm_id = ""
            if payment.payment_method and payment.payment_method.saved:
                pm_id = payment.payment_method.id
            return {
                "event": "subscription_created",
                "app_session_id": metadata.get("app_session_id"),
                "plan_id": metadata.get("plan_id"),
                "photo_limit": metadata.get("photo_limit"),
                "payment_method_id": pm_id,
            }

        if pay_type == "subscription_renewal":
            return {
                "event": "subscription_renewed",
                "app_session_id": metadata.get("app_session_id"),
                "plan_id": metadata.get("plan_id"),
                "photo_limit": metadata.get("photo_limit"),
                "payment_method_id": metadata.get("payment_method_id", ""),
            }

    # ── Payment canceled ──
    if event_type == "payment.canceled" and payment.status == "canceled":
        pay_type = metadata.get("type")
        if pay_type in ("subscription", "subscription_renewal"):
            return {
                "event": "subscription_cancelled",
                "app_session_id": metadata.get("app_session_id"),
            }

    return None
