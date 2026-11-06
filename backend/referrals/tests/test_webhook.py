import pytest
from rest_framework.test import APIClient

from referrals.models import Offer, Referral, ReferralEvent

pytestmark = pytest.mark.django_db

PAYLOAD = {
    "event_id": "evt-abc-123",
    "external_id": "lead-90001",
    "customer_name": "Jordan Sample",
    "customer_email": "jordan.sample@example.com",
    "customer_phone": "555-0101",
    "state": "CO",
    "postal_code": "80202",
    "estimated_price": 450_000,
    "intent_level": "hot",
}


def post_webhook(payload, token="dev-webhook-secret"):
    client = APIClient()
    return client.post(
        "/api/webhooks/referrals/", payload, format="json", headers={"X-Webhook-Token": token}
    )


def test_webhook_requires_token(db):
    response = post_webhook(PAYLOAD, token="wrong")
    assert response.status_code == 403
    assert Referral.objects.count() == 0


def test_webhook_rejects_incomplete_payload(db):
    response = post_webhook({"event_id": "evt-1"})
    assert response.status_code == 400
    assert "external_id" in response.data["fields"]


def test_webhook_creates_referral_and_offers(make_agent):
    make_agent("agent.one", performance_score=0.9)
    make_agent("agent.two", performance_score=0.6)

    response = post_webhook(dict(PAYLOAD, event_id="evt-create-1"))
    assert response.status_code == 201

    referral = Referral.objects.get(external_id="lead-90001")
    assert referral.status == Referral.Status.OFFERED
    assert referral.customer_name == "Jordan Sample"
    assert Offer.objects.filter(referral=referral).count() > 0
    event_types = set(referral.events.values_list("event_type", flat=True))
    assert ReferralEvent.Type.REFERRAL_RECEIVED in event_types
    assert ReferralEvent.Type.OFFER_SENT in event_types


def test_second_delivery_for_same_lead_is_ignored(make_agent):
    make_agent()

    first = post_webhook(dict(PAYLOAD, event_id="evt-first"))
    offers_after_first = Offer.objects.count()
    second = post_webhook(dict(PAYLOAD, event_id="evt-second"))

    assert first.status_code == 201
    assert second.status_code == 200
    assert second.data == {"status": "duplicate_ignored", "referral_id": first.data["referral_id"]}
    assert Referral.objects.filter(external_id=PAYLOAD["external_id"]).count() == 1
    assert Offer.objects.count() == offers_after_first


def test_same_referrals(make_agent):
    """OPERATIONS_REPORTS.md, Report 2: upstream delivered lead-77401 twice, two minutes
    apart, with different event_ids (evt-9f21c, evt-a03d7). Both used to create a referral
    and send offers."""
    make_agent()
    lead = {
        "external_id": "lead-77401",
        "customer_name": "Rowan Mockwell",
        "customer_email": "rowan.mockwell@example.com",
        "customer_phone": "555-0114",
        "state": "CO",
        "postal_code": "80231",
        "estimated_price": 610_000,
        "intent_level": "warm",
    }

    first = post_webhook(dict(lead, event_id="evt-9f21c"))
    offers_after_first = Offer.objects.count()
    retry = post_webhook(dict(lead, event_id="evt-a03d7"))

    assert first.status_code == 201
    assert retry.status_code == 200
    assert retry.data == {"status": "duplicate_ignored", "referral_id": first.data["referral_id"]}
    assert Referral.objects.filter(external_id="lead-77401").count() == 1
    assert Offer.objects.count() == offers_after_first
