"""Audit/event trail helpers."""

from .base import ReferralEvent

# TODO: Same, would move this into the domain model.
def record_event(referral, event_type, actor="", payload=None, **kwargs):
    event_id = None
    # Only track event_id when referral is received:
    if payload and event_type == ReferralEvent.Type.REFERRAL_RECEIVED:
        event_id = payload.get('event_id') or None

    return ReferralEvent.objects.create(
        referral=referral,
        event_type=event_type,
        actor=actor,
        payload=payload or {},
        event_id=event_id,
    )
