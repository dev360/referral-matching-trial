"""Resolve referrals that share an external_id before uniqueness is enforced.

Upstream retries could create several referrals for one lead (Report 2). For each
external_id we keep one canonical referral and mark the rest as duplicates:

1. If agents have claimed copies, the earliest claim wins: that agent most likely
   contacted the customer first. When more than one copy is claimed, every claimed
   copy also gets a claim_conflicted event, because only Ops can tell which agent
   the customer is actually working with.
2. Otherwise the oldest copy wins: it went through matching first and holds the
   lead's real history.

Nothing is deleted: duplicates keep their history and get an audit event pointing
at the canonical referral.
"""

from django.db import migrations
from django.db.models import Count, Min


def mark_duplicates(apps, schema_editor):
    Referral = apps.get_model("referrals", "Referral")
    Claim = apps.get_model("referrals", "Claim")
    Offer = apps.get_model("referrals", "Offer")
    ReferralEvent = apps.get_model("referrals", "ReferralEvent")

    shared_ids = (
        Referral.objects.exclude(status="duplicate")
        .values("external_id")
        .annotate(n=Count("id"))
        .filter(n__gt=1)
        .values_list("external_id", flat=True)
    )
    for external_id in shared_ids:
        candidates = list(
            Referral.objects.filter(external_id=external_id)
            .exclude(status="duplicate")
            .order_by("created_at", "pk")
        )
        first_claim_at = dict(
            Claim.objects.filter(referral__in=candidates, active=True)
            .values("referral_id")
            .annotate(first=Min("created_at"))
            .values_list("referral_id", "first")
        )
        claimed = sorted(
            (r for r in candidates if r.pk in first_claim_at),
            key=lambda r: (first_claim_at[r.pk], r.pk),
        )
        canonical = claimed[0] if claimed else candidates[0]

        if len(claimed) > 1:
            for referral in claimed:
                ReferralEvent.objects.create(
                    referral=referral,
                    event_type="claim_conflicted",
                    actor="migration",
                    payload={
                        "external_id": external_id,
                        "kept_referral_id": canonical.pk,
                        "claimed_referral_ids": [r.pk for r in claimed],
                    },
                )

        for referral in candidates:
            if referral.pk == canonical.pk:
                continue
            referral.status = "duplicate"
            referral.save(update_fields=["status"])
            Offer.objects.filter(referral=referral, status="pending").update(status="expired")
            ReferralEvent.objects.create(
                referral=referral,
                event_type="marked_duplicate",
                actor="migration",
                payload={"duplicate_of": canonical.pk, "external_id": external_id},
            )


class Migration(migrations.Migration):
    dependencies = [
        ("referrals", "0003_referral_status_duplicate"),
    ]

    operations = [
        migrations.RunPython(mark_duplicates, migrations.RunPython.noop),
    ]
