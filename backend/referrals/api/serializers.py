from rest_framework import serializers

from referrals.models import Agent, Claim, Offer, Referral, ReferralEvent


class AgentSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Agent
        fields = ["id", "name", "email", "performance_score", "active_referral_count", "capacity"]


class ReferralSerializer(serializers.ModelSerializer):
    assigned_agent = AgentSummarySerializer(read_only=True)

    class Meta:
        model = Referral
        fields = [
            "id",
            "external_id",
            "customer_name",
            "customer_email",
            "customer_phone",
            "state",
            "postal_code",
            "estimated_price",
            "intent_level",
            "status",
            "assigned_agent",
            "created_at",
        ]


class OfferSerializer(serializers.ModelSerializer):
    referral = ReferralSerializer(read_only=True)

    class Meta:
        model = Offer
        fields = [
            "id",
            "referral",
            "score",
            "score_explanation",
            "eligibility_snapshot",
            "status",
            "offered_at",
            "expires_at",
            "responded_at",
        ]


class ReferralEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReferralEvent
        fields = ["id", "event_type", "actor", "payload", "created_at"]


class ClaimSerializer(serializers.ModelSerializer):
    agent = AgentSummarySerializer(read_only=True)

    class Meta:
        model = Claim
        fields = ["id", "agent", "active", "created_at", "released_at"]


class AssignedAgentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Agent
        fields = [
            "id",
            "name",
            "email",
        ]


class OpsOfferSerializer(serializers.ModelSerializer):
    agent = serializers.CharField(source="agent.name", read_only=True)

    class Meta:
        model = Offer
        fields = [
            'id',
            'agent',
            'score',
            'status',
            'offered_at',
            'expires_at',
        ]


class OpsReferralSerializer(serializers.ModelSerializer):
    assigned_agent = AssignedAgentSerializer(read_only=True)
    offers = OpsOfferSerializer(many=True, read_only=True)
    events = ReferralEventSerializer(many=True, read_only=True)
    age_minutes = serializers.SerializerMethodField()

    class Meta:
        model = Referral
        fields = [
            "id",
            "external_id",
            "customer_name",
            "state",
            "postal_code",
            "estimated_price",
            "intent_level",
            "status",
            "assigned_agent",
            "age_minutes",
            "offers",
            "events",
            "created_at",
        ]

    # TODO: This doesn't belong in an api imho.. handle it in frontend.
    def get_age_minutes(self, obj):
        from django.utils import timezone

        return int((timezone.now() - obj.created_at).total_seconds() // 60)
