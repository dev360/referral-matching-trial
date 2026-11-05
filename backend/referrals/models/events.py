"""Audit/event trail helpers."""

from django.db import transaction, IntegrityError

from .base import ReferralEvent


class EventExists(Exception):
    def __init__(self, *args, **kwargs):
        self.referral_event = kwargs["referral_event"]


# TODO: Same, would move this into the domain model.
def record_event(referral, event_type, actor="", payload=None, **kwargs):
    event_id = None
    # Only track event_id when referral is received:
    if payload and event_type == ReferralEvent.Type.REFERRAL_RECEIVED:
        event_id = payload.get("event_id") or None

    try:
        with transaction.atomic():
            return ReferralEvent.objects.create(
                referral=referral,
                event_type=event_type,
                actor=actor,
                payload=payload or {},
                event_id=event_id,
            )
    except IntegrityError as exc:
        referral_event = ReferallEvent.objects.get(event_id=event_id)
        raise EventExists(event_id, referral_event=referral_event)
