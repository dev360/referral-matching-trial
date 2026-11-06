"""Referral creation helpers."""

from django.db import IntegrityError, transaction

from .base import Referral


class ReferralExists(Exception):
    def __init__(self, external_id, referral):
        super().__init__(f"referral {external_id} already exists")
        self.external_id = external_id
        self.referral = referral


def create_referral(**kwargs):
    """Create a referral, or raise ReferralExists if its external_id is already taken."""
    try:
        with transaction.atomic():
            return Referral.objects.create(**kwargs)
    except IntegrityError as exc:
        existing = (
            Referral.objects.filter(external_id=kwargs.get("external_id"))
            .exclude(status=Referral.Status.DUPLICATE)
            .first()
        )
        if existing is None:
            raise
        raise ReferralExists(existing.external_id, existing) from exc
