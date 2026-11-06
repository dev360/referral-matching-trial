import importlib
from datetime import timedelta

import pytest
from django.apps import apps
from django.db import connection
from django.utils import timezone

from referrals.models import Claim, Offer, Referral, ReferralEvent

pytestmark = pytest.mark.django_db

mark_duplicates = importlib.import_module(
    "referrals.migrations.0004_mark_duplicate_referrals"
).mark_duplicates

UNIQUE_EXTERNAL_ID = next(
    c for c in Referral._meta.constraints if c.name == "uniq_referral_external_id_unless_duplicate"
)


@pytest.fixture
def legacy_schema():
    """The schema as it was before 0005, when duplicate external_ids were possible.

    Postgres DDL is transactional, so the dropped constraint comes back when the test's
    transaction rolls back.
    """
    with connection.schema_editor() as editor:
        editor.remove_constraint(Referral, UNIQUE_EXTERNAL_ID)


def _restore_constraint():
    """Re-adding the constraint proves the migration left no conflicting rows."""
    with connection.cursor() as cursor:
        # Flush deferred FK checks; Postgres won't build an index while they are pending.
        cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")
    with connection.schema_editor() as editor:
        editor.add_constraint(Referral, UNIQUE_EXTERNAL_ID)


def test_migration_keeps_oldest_referral_when_none_claimed(
    legacy_schema, make_agent, make_referral, make_offer
):
    agent = make_agent()
    now = timezone.now()
    original = make_referral(external_id="lead-77401")
    retry = make_referral(external_id="lead-77401")
    Referral.objects.filter(pk=original.pk).update(created_at=now - timedelta(minutes=2))
    Referral.objects.filter(pk=retry.pk).update(created_at=now)
    retry_offer = make_offer(retry, agent)

    mark_duplicates(apps, None)

    original.refresh_from_db()
    retry.refresh_from_db()
    retry_offer.refresh_from_db()
    assert original.status == Referral.Status.NEW
    assert retry.status == Referral.Status.DUPLICATE
    assert retry_offer.status == Offer.Status.EXPIRED
    event = retry.events.get(event_type=ReferralEvent.Type.MARKED_DUPLICATE)
    assert event.payload == {"duplicate_of": original.pk, "external_id": "lead-77401"}
    _restore_constraint()


def test_migration_keeps_claimed_referral_over_older_one(legacy_schema, make_agent, make_referral):
    agent = make_agent()
    now = timezone.now()
    original = make_referral(external_id="lead-77401")
    retry = make_referral(
        external_id="lead-77401", status=Referral.Status.ASSIGNED, assigned_agent=agent
    )
    Referral.objects.filter(pk=original.pk).update(created_at=now - timedelta(minutes=2))
    Claim.objects.create(referral=retry, agent=agent)

    mark_duplicates(apps, None)

    original.refresh_from_db()
    retry.refresh_from_db()
    assert original.status == Referral.Status.DUPLICATE
    assert retry.status == Referral.Status.ASSIGNED
    _restore_constraint()


def test_agent_cannot_claim_offer_on_duplicate_referral(
    make_agent, make_referral, make_offer, client_for
):
    agent = make_agent()
    referral = make_referral(status=Referral.Status.DUPLICATE)
    offer = make_offer(referral, agent)

    response = client_for(agent.user).post(f"/api/offers/{offer.id}/claim/")

    assert response.status_code == 400
    assert response.data["code"] == "duplicate_referral"
    assert not Claim.objects.filter(referral=referral).exists()


def test_migration_keeps_earliest_claim_and_flags_conflict_when_both_claimed(
    legacy_schema, make_agent, make_referral
):
    first_agent = make_agent("agent.first")
    second_agent = make_agent("agent.second")
    now = timezone.now()
    older = make_referral(
        external_id="lead-77401", status=Referral.Status.ASSIGNED, assigned_agent=second_agent
    )
    newer = make_referral(
        external_id="lead-77401", status=Referral.Status.ASSIGNED, assigned_agent=first_agent
    )
    Referral.objects.filter(pk=older.pk).update(created_at=now - timedelta(minutes=2))
    # The newer copy was claimed first, so its agent most likely reached the customer first.
    late_claim = Claim.objects.create(referral=older, agent=second_agent)
    early_claim = Claim.objects.create(referral=newer, agent=first_agent)
    Claim.objects.filter(pk=early_claim.pk).update(created_at=now - timedelta(minutes=1))
    Claim.objects.filter(pk=late_claim.pk).update(created_at=now)

    mark_duplicates(apps, None)

    older.refresh_from_db()
    newer.refresh_from_db()
    assert newer.status == Referral.Status.ASSIGNED
    assert older.status == Referral.Status.DUPLICATE
    for referral in (older, newer):
        conflict = referral.events.get(event_type=ReferralEvent.Type.CLAIM_CONFLICTED)
        assert conflict.payload == {
            "external_id": "lead-77401",
            "kept_referral_id": newer.pk,
            "claimed_referral_ids": [newer.pk, older.pk],
        }
    _restore_constraint()
