# Decision Note — Christian Toivola

_Aim for roughly one page. Bullet points are fine._

## What I investigated

I read through the brief, operations brief, made a quick prioritized list.

Then I started looking primarily at the webhook endpoint, and at the models. Since 
the static variable at the top for the event_ids stuck out like a sore thumb, I 
worked on that first, then knocked out the database issues on the ops endpoint. 

Not until later did I realize that there were more problems 
around the claiming code, so I went back to that.


## What I prioritized, and why

I honed in on the "one customer / two referrals" and "two agents, one customer" 
sounded like the worst offenders. I also wanted to knock out the dashboard since 
those are usually small fixes. I also identified the "referrals going quiet" as 
being the biggest long-term product problem to solve, but kind of deferred trying 
to look into it because it seemed less pressing.

## What I intentionally deferred

I tried to stick to time limit, so I didn't get to look much at UI.

## Assumptions

I was a little bit unsure of whether it was correct for the upstream system to send
the same external_id multiple times.

## How I validated my work

I added tests, but could have had better test coverage - it was definitively rushed.

## AI usage

I didn't use AI in the analysis, or the coding, except for a few test cases, mostly
because I thought you wanted me to do this without AI.

## Remaining launch risks

The biggest product risk, to me at least, was with referrals going silent. I think 
it undermines trust especially in a marketplace type of app (customers and agents).

There were more issues in the claim code which needed to be fixed, which were around
notifications failing. I would make sure that you always have either a valid phone 
number or a valid email address for a customer/referral, and handle that up-stream
before it reaches this service. This is where I left off, and it started going into
the "referrals going silent" direction by accident.
