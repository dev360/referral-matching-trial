import pytest

from django.db import connection

from django.test.utils import CaptureQueriesContext

from referrals.models import Claim, Referral, ReferralEvent

pytestmark = pytest.mark.django_db



def test_dashboard_requires_ops_role(make_agent, client_for):
    agent = make_agent()
    response = client_for(agent.user).get("/api/ops/referrals/")
    assert response.status_code == 403


def test_dashboard_lists_referrals(make_user, make_referral, client_for):
    ops = make_user("ops.test", is_staff=True)
    make_referral()
    response = client_for(ops).get("/api/ops/referrals/")
    assert response.status_code == 200
    assert len(response.data) == 1
    assert response.data[0]["external_id"] == "lead-test-1"


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
