"""Audit/event trail helpers."""

from .models import ReferralEvent


def record_event(referral, event_type, event_id, actor="", payload=None):
    return ReferralEvent.objects.create(
        referral=referral,
        event_type=event_type,
        event_id=event_id,
        actor=actor,
        payload=payload or {},
    )
