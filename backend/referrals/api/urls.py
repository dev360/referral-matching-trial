from django.urls import path


from . import views, webhooks


urlpatterns = [
    path("webhooks/referrals/", webhooks.intake_referral, name="intake-referral"),
    path("offers/mine/", views.my_offers, name="my-offers"),
    path("offers/<int:offer_id>/claim/", views.claim_offer, name="claim-offer"),
    path("offers/<int:offer_id>/decline/", views.decline_offer, name="decline-offer"),
    path("referrals/<int:referral_id>/", views.referral_detail, name="referral-detail"),
    path("ops/referrals/", views.ops_referrals, name="ops-referrals"),
    path(
        "ops/referrals/<int:referral_id>/events/",
        views.ops_referral_events,
        name="ops-referral-events",
    ),
    path(
        "ops/referrals/<int:referral_id>/override/",
        views.ops_override,
        name="ops-override",
    ),
]
