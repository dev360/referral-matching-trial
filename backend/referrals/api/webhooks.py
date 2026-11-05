"""Intake webhook for referrals delivered by the upstream lead platform."""

import logging

from django.conf import settings
from rest_framework import status
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.response import Response

from referrals import matching
from referrals.events import record_event
from referrals.models import Referral, ReferralEvent

logger = logging.getLogger("referrals.webhooks")

REQUIRED_FIELDS = [
    "event_id",
    "external_id",
    "customer_name",
    "customer_email",
    "customer_phone",
    "state",
    "postal_code",
    "estimated_price",
]


@api_view(["POST"])
@authentication_classes([])
@permission_classes([])
def intake_referral(request):
    if request.headers.get("X-Webhook-Token") != settings.WEBHOOK_TOKEN:
        return Response({"detail": "invalid webhook token"}, status=status.HTTP_403_FORBIDDEN)

    payload = request.data
    missing = [f for f in REQUIRED_FIELDS if not payload.get(f)]
    if missing:
        return Response(
            {"detail": "missing fields", "fields": missing},
            status=status.HTTP_400_BAD_REQUEST,
        )

    event_id = str(payload["event_id"])
    # Check if an event has been processed in postgres:
    if ReferralEvent.event_exists(event_id):
        logger.info("duplicate delivery ignored: event_id=%s", event_id)
        return Response({"status": "duplicate_ignored", "event_id": event_id})

    referral = Referral.objects.create(
        external_id=payload["external_id"],
        customer_name=payload["customer_name"],
        customer_email=payload["customer_email"],
        customer_phone=payload["customer_phone"],
        state=payload["state"],
        postal_code=payload["postal_code"],
        estimated_price=int(payload["estimated_price"]),
        intent_level=payload.get("intent_level", Referral.Intent.WARM),
    )
    record_event(
        referral,
        ReferralEvent.Type.REFERRAL_RECEIVED,
        actor="intake-webhook",
        payload={"event_id": event_id},
    )

    offers = matching.build_offers(referral)
    _PROCESSED_EVENT_IDS.add(event_id)

    logger.info(
        "referral ingested: event_id=%s external_id=%s offers=%d",
        event_id,
        referral.external_id,
        len(offers),
    )
    return Response(
        {"status": "created", "referral_id": referral.id, "offers": len(offers)},
        status=status.HTTP_201_CREATED,
    )
