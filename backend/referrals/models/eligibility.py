"""Hard eligibility rules for offering or claiming a referral.

An agent may work a referral only when every rule below holds.
"""


# TODO:.. this smells like validation / eligibility code..
# May come back to this and move it later.
def evaluate(agent, referral):
    """Return a snapshot dict: {"eligible": bool, "reasons": [str, ...]}."""
    reasons = []
    if not agent.active:
        reasons.append("agent_inactive")
    if agent.suspended:
        reasons.append("agent_suspended")
    if referral.state not in (agent.licensed_states or []):
        reasons.append("not_licensed_in_state")
    if not _in_service_area(agent, referral):
        reasons.append("outside_service_area")
    if not (agent.minimum_price <= referral.estimated_price <= agent.maximum_price):
        reasons.append("price_out_of_range")
    if agent.active_referral_count >= agent.capacity:
        reasons.append("at_capacity")
    return {"eligible": not reasons, "reasons": reasons}


def _in_service_area(agent, referral):
    prefixes = agent.service_area_zip_prefixes or []
    return any(referral.postal_code.startswith(p) for p in prefixes)
