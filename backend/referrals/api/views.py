from django.shortcuts import get_object_or_404
from django.db.models import Prefetch
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import BasePermission
from rest_framework.response import Response

from referrals.models import Agent, Claim, Offer, Referral, ReferralEvent, claims
from referrals.models.events import record_event

from referrals.api.serializers import (
    OfferSerializer,
    OpsReferralSerializer,
    ReferralEventSerializer,
    ReferralSerializer,
)


class IsOpsUser(BasePermission):
    message = "Operations access required."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_staff)


# TODO: Consider putting in mw; request.agent_profile
def _agent_for(request):
    return getattr(request.user, "agent_profile", None)


@api_view(["GET"])
def my_offers(request):
    """Offers for the signed-in agent's queue."""
    agent = _agent_for(request)
    if agent is None:
        return Response({"detail": "No agent profile."}, status=status.HTTP_403_FORBIDDEN)

    now = timezone.now()
    stale = Offer.objects.filter(agent=agent, status=Offer.Status.PENDING, expires_at__lt=now)
    for offer in stale:
        offer.status = Offer.Status.EXPIRED
        offer.save(update_fields=["status"])
        record_event(
            offer.referral,
            ReferralEvent.Type.OFFER_EXPIRED,
            actor="system",
            payload={"offer_id": offer.id},
        )

    offers = (
        Offer.objects.filter(agent=agent, status=Offer.Status.PENDING)
        .select_related("referral", "referral__assigned_agent")
        .order_by("expires_at")
    )
    return Response(OfferSerializer(offers, many=True).data)


@api_view(["GET"])
def referral_detail(request, referral_id):
    referral = get_object_or_404(Referral, pk=referral_id)
    return Response(ReferralSerializer(referral).data)


@api_view(["POST"])
def claim_offer(request, offer_id):
    agent = _agent_for(request)
    if agent is None:
        return Response({"detail": "No agent profile."}, status=status.HTTP_403_FORBIDDEN)

    offer = get_object_or_404(Offer, pk=offer_id, agent=agent)
    try:
        claim = claims.claim_offer(offer, agent)
    except claims.ClaimError as exc:
        return Response({"detail": str(exc), "code": exc.code}, status=status.HTTP_400_BAD_REQUEST)
    return Response({"status": "claimed", "claim_id": claim.id, "referral_id": offer.referral_id})


@api_view(["POST"])
def decline_offer(request, offer_id):
    agent = _agent_for(request)
    if agent is None:
        return Response({"detail": "No agent profile."}, status=status.HTTP_403_FORBIDDEN)

    offer = get_object_or_404(Offer, pk=offer_id, agent=agent)
    try:
        claims.decline_offer(offer, agent)
    except claims.ClaimError as exc:
        return Response({"detail": str(exc), "code": exc.code}, status=status.HTTP_400_BAD_REQUEST)
    return Response({"status": "declined", "offer_id": offer.id})


@api_view(["GET"])
@permission_classes([IsOpsUser])
def ops_referrals(request):
    # First off: Not at all a fan of function based views for DRF; it takes away the primary way
    # that you override functionality (by overriding classes). Theres a learning curve, yes,
    # but once you understand it, you understand the request cycle.
    referrals = (
        Referral.objects.all()
        .order_by("-created_at")
        .select_related("assigned_agent")
        .prefetch_related(
            Prefetch(
                "offers",
                queryset=Offer.objects.select_related("agent").order_by("-offered_at")
            ),
            "events",
        )
    )
    response = Response(OpsReferralSerializer(referrals, many=True).data)
    return response


@api_view(["GET"])
@permission_classes([IsOpsUser])
def ops_referral_events(request, referral_id):
    referral = get_object_or_404(Referral, pk=referral_id)
    return Response(ReferralEventSerializer(referral.events.all(), many=True).data)


@api_view(["POST"])
@permission_classes([IsOpsUser])
def ops_override(request, referral_id):
    """Operations reassigns (or unassigns) a referral."""

    referral = get_object_or_404(Referral, pk=referral_id)
    agent_id = request.data.get("agent_id")
    note = request.data.get("note", "")

    previous_agent = referral.assigned_agent
    Claim.objects.filter(referral=referral, active=True).update(
        active=False, released_at=timezone.now()
    )

    if agent_id is None:
        referral.assigned_agent = None
        referral.status = Referral.Status.NEW
    else:
        agent = get_object_or_404(Agent, pk=agent_id)
        Claim.objects.create(referral=referral, agent=agent)
        referral.assigned_agent = agent
        referral.status = Referral.Status.ASSIGNED

    referral.save(update_fields=["assigned_agent", "status"])
    record_event(
        referral,
        ReferralEvent.Type.OPS_OVERRIDE,
        actor=request.user.get_username(),
        payload={
            "previous_agent_id": previous_agent.id if previous_agent else None,
            "new_agent_id": agent_id,
            "note": note,
        },
    )
    return Response({"status": "overridden", "referral_id": referral.id})
