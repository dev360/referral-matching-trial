

# Steps:

## Clone, get running
- The code base is about referral matching. Receives referrals matches it with agents and ranks matches. 
  Sounds like a block and score type of algorithm.

- Objective:
  - Increase the qualified referrals
  - Time limit of 10 minutes
  - No double assignments
  - No leakage of sensitive information
  - Dashboard telemetry should be correct
  - Follow domain rules for the matching

- Operations reports show concerns with existing app
- Not expected to fix everything; prioritize accordingly and maintain running state


## Analysis of Operations reports

- An agent in one state can see customers in other states (who should clearly not have access according to rules), 
**Theory: Bug? Code is matching customers that should not be eligible for match **

- Two referall records matching one request, identical information, but minutes apart
**Theory: Maybe its a customer clicking again, since there is substantial time gap**

- Two agents, one customer;
**Theory: this sounds more like a potential race condition. Since data only shows one agent assigned, it may be overwriting the assigned agent.**

- Referrals going quiet
**Theory: Logic bug; needs a timeout window, or prioritize agents that respond faster**

- Agent customer referrals disappearing from assigned list

- Dashboard slow
**Theory: probably database issues or endpoints**

**Logs**

- One excerpt indicates one external lead is processed twice; 2 minutes apart. Could be failing the processing?

- Two claims came very close together - within ~= 15 ms - enough to be a race condition if code is not transactional etc. If this code is involved in the "two agents, one customer" code, then could be smoking gun.
- Other note: referral above shows assigned, but there is no claim_succeeded entry; only claim_attempted.


- Other: Claim says nice work, but card disappears and no error displayed.. 


## Quick triage:

### Low level, quick wins:
- Display error messages when claiming fails in UI
- Dashboard loading .. this is probably something dumb. But its not as important in relation to others.

### More important, need deeper dive/exploration
- Potential Bug: Data leakage (e.g. match when shouldnt match?)
- Potential Bug: Race condition?
- Potential Bug: UI allowing you to "rematch"; e.g. undoing a match?
- Potential Bug: Not sure, but I get impression referrals going quiet may be biggest issue


This is my thinking of how to priortize analysis:
- Referrals going quiet undermines the overall functioning and revenue of the system from a customer perspective. In a high-volume marketplace, 
  this would be the biggest product feature to try to fix. Theory: Customers are more in a hurry to be matched with a 
  good match than agents with a potential client. So this would be my heuristic for this.
- Data leakage (of a potentially non matching customer) - I could be completely wrong, but this sounds like an agent was matched with 
  a candidate that they should never have been matched with. This undermines the functioning of the system both from an agent and customer perspective.
  If there are very few matching combinations, this could be a distribution problem that cant be solved by code (e.g. not neccessarily a bug per se).
- UI "double click", or reprocessing bugs; this would probably be pretty common thing people do - not sure if I put this at medium importance.
- Other: the dashboard slowness.. I feel like this is important, probably easy to fix. I'd be tempted to knock it out fast just for a moral boost.

