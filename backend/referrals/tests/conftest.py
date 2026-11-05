from datetime import timedelta

import pytest
from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from referrals.models import Agent, Offer, Referral, ReferralEvent


@pytest.fixture
def make_user(db):
    def _make(username, is_staff=False):
        user = User.objects.create_user(username=username, password="x", is_staff=is_staff)
        Token.objects.create(user=user, key=f"tok-{username}"[:40])
        return user

    return _make


@pytest.fixture
def make_agent(make_user):
    def _make(username="agent.test", **kwargs):
        user = make_user(username)
        defaults = dict(
            name=username.replace(".", " ").title(),
            email=f"{username}@example.com",
            active=True,
            suspended=False,
            licensed_states=["CO"],
            service_area_zip_prefixes=["802"],
            minimum_price=200_000,
            maximum_price=1_100_000,
            capacity=5,
            active_referral_count=1,
            performance_score=0.8,
        )
        defaults.update(kwargs)
        return Agent.objects.create(user=user, **defaults)

    return _make


@pytest.fixture
def make_referral(db):
    def _make(**kwargs):
        defaults = dict(
            external_id="lead-test-1",
            customer_name="Casey Example",
            customer_email="casey.example@example.com",
            customer_phone="555-0100",
            state="CO",
            postal_code="80202",
            estimated_price=500_000,
        )
        defaults.update(kwargs)
        return Referral.objects.create(**defaults)

    return _make


@pytest.fixture
def make_referrals(db):
    def _make(**kwargs):
        for i in range(10):
            defaults = dict(
                external_id=f"lead-test-{i}",
                customer_name=f"Casey Example {i}",
                customer_email="casey-{i}.example@example.com",
                customer_phone="555-010{i}",
                state="CO",
                postal_code=f"8020{i}",
                estimated_price=500_000,
            )
            defaults.update(kwargs)
            Referral.objects.create(**defaults)

    return _make


@pytest.fixture
def make_offer(db):
    def _make(referral, agent, offered_at=None, **kwargs):
        offered_at = offered_at or timezone.now()
        defaults = dict(
            score=0.5,
            eligibility_snapshot={"eligible": True, "reasons": []},
            expires_at=offered_at + timedelta(minutes=10),
        )
        defaults.update(kwargs)
        offer = Offer.objects.create(referral=referral, agent=agent, **defaults)
        # offered_at is auto_now_add, so it can only be overridden after creation.
        Offer.objects.filter(pk=offer.pk).update(offered_at=offered_at)
        offer.refresh_from_db()
        return offer

    return _make


@pytest.fixture
def make_event(db):
    def _make(referral, event_type, created_at=None, **kwargs):
        event = ReferralEvent.objects.create(referral=referral, event_type=event_type, **kwargs)
        if created_at is not None:
            # created_at is auto_now_add, so it can only be overridden after creation.
            ReferralEvent.objects.filter(pk=event.pk).update(created_at=created_at)
            event.refresh_from_db()
        return event

    return _make


@pytest.fixture
def client_for():
    def _client(user):
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Token {user.auth_token.key}")
        return client

    return _client
