import pytest

from referrals.models import eligibility

pytestmark = pytest.mark.django_db


def test_fully_eligible_agent(make_agent, make_referral):
    agent = make_agent()
    referral = make_referral()
    snapshot = eligibility.evaluate(agent, referral)
    assert snapshot == {"eligible": True, "reasons": []}


@pytest.mark.parametrize(
    "agent_kwargs,referral_kwargs,expected_reason",
    [
        ({"active": False}, {}, "agent_inactive"),
        ({"suspended": True}, {}, "agent_suspended"),
        ({"licensed_states": ["TX"]}, {}, "not_licensed_in_state"),
        ({"service_area_zip_prefixes": ["750"]}, {}, "outside_service_area"),
        ({"minimum_price": 600_000}, {"estimated_price": 500_000}, "price_out_of_range"),
        ({"maximum_price": 400_000}, {"estimated_price": 500_000}, "price_out_of_range"),
        ({"capacity": 2, "active_referral_count": 2}, {}, "at_capacity"),
    ],
)
def test_ineligible_reasons(
    make_agent, make_referral, agent_kwargs, referral_kwargs, expected_reason
):
    agent = make_agent(**agent_kwargs)
    referral = make_referral(**referral_kwargs)
    snapshot = eligibility.evaluate(agent, referral)
    assert snapshot["eligible"] is False
    assert expected_reason in snapshot["reasons"]
