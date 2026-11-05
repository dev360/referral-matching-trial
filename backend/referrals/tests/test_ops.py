from datetime import timedelta

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from referrals.models import Claim, Offer, Referral, ReferralEvent

pytestmark = pytest.mark.django_db


def _iso(dt):
    """Match DRF's datetime rendering."""
    return dt.isoformat().replace("+00:00", "Z")


def test_dashboard_requires_ops_role(make_agent, client_for):
    agent = make_agent()
    response = client_for(agent.user).get("/api/ops/referrals/")
    assert response.status_code == 403


def test_dashboard_lists_referrals(
    make_user, make_agent, make_referral, make_offer, make_event, client_for
):
    ops = make_user("ops.test", is_staff=True)
    winner = make_agent("agent.winner")
    decliner = make_agent("agent.decliner")
    sleeper = make_agent("agent.sleeper")
    referral = make_referral(status=Referral.Status.ASSIGNED, assigned_agent=winner)
    Claim.objects.create(referral=referral, agent=winner)
    t0 = timezone.now().replace(microsecond=0) - timedelta(hours=1)

    # Inserted oldest first; the endpoint must return them newest first.
    make_offer(
        referral,
        winner,
        offered_at=t0 + timedelta(minutes=1),
        score=0.91,
        status=Offer.Status.ACCEPTED,
    )
    make_offer(
        referral,
        decliner,
        offered_at=t0 + timedelta(minutes=2),
        score=0.82,
        status=Offer.Status.DECLINED,
    )
    newest_offer = make_offer(
        referral,
        sleeper,
        offered_at=t0 + timedelta(minutes=3),
        score=0.73,
        status=Offer.Status.EXPIRED,
    )

    # Inserted newest first; the endpoint must return them oldest first.
    make_event(
        referral,
        ReferralEvent.Type.CLAIM_SUCCEEDED,
        created_at=t0 + timedelta(minutes=14),
        actor=winner.name,
    )
    make_event(
        referral,
        ReferralEvent.Type.OFFER_EXPIRED,
        created_at=t0 + timedelta(minutes=13),
        actor="system",
    )
    make_event(
        referral,
        ReferralEvent.Type.OFFER_DECLINED,
        created_at=t0 + timedelta(minutes=5),
        actor=decliner.name,
    )
    make_event(
        referral,
        ReferralEvent.Type.CANDIDATES_GENERATED,
        created_at=t0 + timedelta(minutes=1),
        actor="matching",
        payload={"considered": 3},
    )
    first_event = make_event(
        referral,
        ReferralEvent.Type.REFERRAL_RECEIVED,
        created_at=t0,
        actor="intake-webhook",
        payload={"event_id": "evt-1"},
    )

    response = client_for(ops).get("/api/ops/referrals/")

    assert response.status_code == 200
    [row] = response.json()
    assert row["external_id"] == referral.external_id
    assert row["status"] == Referral.Status.ASSIGNED
    assert row["assigned_agent"] == {"id": winner.id, "name": winner.name, "email": winner.email}

    assert len(row["offers"]) == 3
    assert row["offers"][0] == {
        "id": newest_offer.id,
        "agent": sleeper.name,
        "score": newest_offer.score,
        "status": newest_offer.status,
        "offered_at": _iso(newest_offer.offered_at),
        "expires_at": _iso(newest_offer.expires_at),
    }

    assert len(row["events"]) == 5
    assert row["events"][0] == {
        "id": first_event.id,
        "event_type": first_event.event_type,
        "actor": first_event.actor,
        "payload": first_event.payload,
        "created_at": _iso(first_event.created_at),
    }


def test_dashboard_referall_query_count(make_user, make_referrals, client_for):
    ops = make_user("ops.test", is_staff=True)
    make_referrals()
    with CaptureQueriesContext(connection) as queries:
        response = client_for(ops).get("/api/ops/referrals/")

    assert response.status_code == 200
    assert len(queries) == 2


def test_override_reassigns_and_records_event(make_user, make_agent, make_referral, client_for):
    ops = make_user("ops.test", is_staff=True)
    original = make_agent("agent.original")
    replacement = make_agent("agent.replacement")
    referral = make_referral(status=Referral.Status.ASSIGNED, assigned_agent=original)
    Claim.objects.create(referral=referral, agent=original)

    response = client_for(ops).post(
        f"/api/ops/referrals/{referral.id}/override/",
        {"agent_id": replacement.id, "note": "customer requested"},
        format="json",
    )
    assert response.status_code == 200

    referral.refresh_from_db()
    assert referral.assigned_agent_id == replacement.id
    assert not Claim.objects.filter(referral=referral, agent=original, active=True).exists()
    assert Claim.objects.filter(referral=referral, agent=replacement, active=True).exists()
    assert referral.events.filter(event_type=ReferralEvent.Type.OPS_OVERRIDE).exists()
