"""Intake webhook for referrals delivered by the upstream lead platform."""

import logging

from django.conf import settings
from django.db import transaction
from rest_framework import status
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.response import Response

from referrals.models import matching
from referrals.models.events import record_event, EventExists
from referrals.models.referrals import ReferralExists, create_referral
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
    if ReferralEvent.event_exists(event_id):
        logger.info("duplicate delivery ignored: event_id=%s", event_id)
        return Response({"status": "duplicate_ignored", "event_id": event_id})

    try:
        with transaction.atomic():
            created = True
            try:
                referral = create_referral(
                    external_id=payload["external_id"],
                    customer_name=payload["customer_name"],
                    customer_email=payload["customer_email"],
                    customer_phone=payload["customer_phone"],
                    state=payload["state"],
                    postal_code=payload["postal_code"],
                    estimated_price=int(payload["estimated_price"]),
                    intent_level=payload.get("intent_level", Referral.Intent.WARM),
                )
            except ReferralExists as ex:
                # Another delivery for a lead we already have: reuse its referral.
                referral = ex.referral
                created = False

            record_event(
                referral,
                ReferralEvent.Type.REFERRAL_RECEIVED,
                actor="intake-webhook",
                payload={"event_id": event_id},
            )
    except EventExists as ex:
        # This would be a pretty rare ABA race condition, but
        # by using this uniqueness catch, our code will be correct:
        logger.info(
            "duplicate delivery ignored: event_id=%s referral_event=%s", event_id, ex.event.pk
        )
        return Response({"status": "duplicate_ignored", "event_id": event_id})

    if not created:
        logger.info(
            "duplicate lead ignored: event_id=%s external_id=%s", event_id, referral.external_id
        )
        return Response({"status": "duplicate_ignored", "referral_id": referral.id})

    offers = matching.build_offers(referral)

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
