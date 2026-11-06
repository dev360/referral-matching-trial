from django.conf import settings
from django.db import models


class Agent(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="agent_profile"
    )
    name = models.CharField(max_length=120)
    email = models.EmailField()
    active = models.BooleanField(default=True)
    suspended = models.BooleanField(default=False)
    licensed_states = models.JSONField(default=list)
    service_area_zip_prefixes = models.JSONField(default=list)
    minimum_price = models.PositiveIntegerField(default=0)
    maximum_price = models.PositiveIntegerField(default=2_000_000)
    capacity = models.PositiveIntegerField(default=5)
    active_referral_count = models.PositiveIntegerField(default=0)
    performance_score = models.FloatField(null=True, blank=True)

    def __str__(self):
        return self.name


class Referral(models.Model):
    class Status(models.TextChoices):
        NEW = "new"
        OFFERED = "offered"
        ASSIGNED = "assigned"
        CLOSED = "closed"
        DUPLICATE = "duplicate"

    class Intent(models.TextChoices):
        BROWSING = "browsing"
        WARM = "warm"
        HOT = "hot"

    external_id = models.CharField(max_length=64, db_index=True)
    customer_name = models.CharField(max_length=120)
    customer_email = models.EmailField()
    customer_phone = models.CharField(max_length=40)
    state = models.CharField(max_length=2)
    postal_code = models.CharField(max_length=10)
    estimated_price = models.PositiveIntegerField()
    intent_level = models.CharField(max_length=16, choices=Intent.choices, default=Intent.WARM)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.NEW)
    assigned_agent = models.ForeignKey(
        Agent, null=True, blank=True, on_delete=models.SET_NULL, related_name="assigned_referrals"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            # One live referral per upstream lead; duplicates are kept for the audit trail.
            models.UniqueConstraint(
                fields=["external_id"],
                condition=~models.Q(status="duplicate"),
                name="uniq_referral_external_id_unless_duplicate",
            ),
        ]

    def __str__(self):
        return f"{self.external_id} ({self.state} {self.postal_code})"


class Offer(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending"
        ACCEPTED = "accepted"
        DECLINED = "declined"
        EXPIRED = "expired"

    referral = models.ForeignKey(Referral, on_delete=models.CASCADE, related_name="offers")
    agent = models.ForeignKey(Agent, on_delete=models.CASCADE, related_name="offers")
    eligibility_snapshot = models.JSONField(default=dict)
    score = models.FloatField()
    score_explanation = models.JSONField(default=dict)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    offered_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    responded_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Offer {self.pk}: {self.referral_id} -> {self.agent_id} ({self.status})"


class Claim(models.Model):
    referral = models.ForeignKey(Referral, on_delete=models.CASCADE, related_name="claims")
    agent = models.ForeignKey(Agent, on_delete=models.CASCADE, related_name="claims")
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    released_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Claim {self.pk}: {self.referral_id} by {self.agent_id}"


class ReferralEvent(models.Model):
    class Type(models.TextChoices):
        REFERRAL_RECEIVED = "referral_received"
        CANDIDATES_GENERATED = "candidates_generated"
        OFFER_SENT = "offer_sent"
        OFFER_VIEWED = "offer_viewed"
        CLAIM_ATTEMPTED = "claim_attempted"
        CLAIM_SUCCEEDED = "claim_succeeded"
        CLAIM_CONFLICTED = "claim_conflicted"
        OFFER_DECLINED = "offer_declined"
        OFFER_EXPIRED = "offer_expired"
        OPS_OVERRIDE = "ops_override"
        MARKED_DUPLICATE = "marked_duplicate"

    referral = models.ForeignKey(Referral, on_delete=models.CASCADE, related_name="events")
    event_type = models.CharField(max_length=32, choices=Type.choices)
    event_id = models.CharField(max_length=64, unique=True, null=True, blank=True)
    actor = models.CharField(max_length=120, blank=True, default="")
    payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    # This is perhaps a little bit too rails-esque but I went for it.
    @classmethod
    def event_exists(cls, event_id):
        return cls.objects.filter(event_id=event_id).exists()

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.referral_id} {self.event_type}"
