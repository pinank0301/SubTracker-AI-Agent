# pyrefly: ignore [missing-import]
import pytest
import os
import sys

# Ensure app is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.schemas.subscription import SubscriptionDTO, BillingCycle, SubscriptionStatus, UsageSignal, BillingHistoryItem


@pytest.fixture
def sample_subscriptions():
    return [
        SubscriptionDTO(
            id="sub-1",
            userId="user-test-123",
            name="Netflix",
            category="Entertainment",
            amount=22.99,
            currency="USD",
            billingCycle=BillingCycle.MONTHLY,
            renewalDate="2026-08-30",
            status=SubscriptionStatus.ACTIVE,
            description="Netflix Premium"
        ),
        SubscriptionDTO(
            id="sub-2",
            userId="user-test-123",
            name="Spotify",
            category="Music",
            amount=11.99,
            currency="USD",
            billingCycle=BillingCycle.MONTHLY,
            renewalDate="2026-09-05",
            status=SubscriptionStatus.ACTIVE,
            description="Spotify Individual"
        ),
        SubscriptionDTO(
            id="sub-3",
            userId="user-test-123",
            name="Gold's Gym",
            category="Fitness",
            amount=55.00,
            currency="USD",
            billingCycle=BillingCycle.MONTHLY,
            renewalDate="2026-08-28",
            status=SubscriptionStatus.ACTIVE,
            description="Gym Membership"
        )
    ]


@pytest.fixture
def sample_usage_signals():
    return [
        UsageSignal(
            subscription_id="sub-1",
            subscription_name="Netflix",
            active_days_last_30=15,
            hours_used_last_30=25.0,
            logins_last_30=20,
            features_used_ratio=0.7,
            engagement_trend="STABLE"
        ),
        UsageSignal(
            subscription_id="sub-2",
            subscription_name="Spotify",
            active_days_last_30=25,
            hours_used_last_30=40.0,
            logins_last_30=35,
            features_used_ratio=0.9,
            engagement_trend="INCREASING"
        ),
        UsageSignal(
            subscription_id="sub-3",
            subscription_name="Gold's Gym",
            active_days_last_30=1,
            hours_used_last_30=1.0,
            logins_last_30=1,
            features_used_ratio=0.1,
            engagement_trend="DORMANT"
        )
    ]


@pytest.fixture
def sample_billing_history():
    return [
        BillingHistoryItem(
            subscription_id="sub-1",
            subscription_name="Netflix",
            billing_date="2026-07-30",
            amount=22.99,
            currency="USD",
            status="PAID",
            price_change_from_previous=12.0
        ),
        BillingHistoryItem(
            subscription_id="sub-2",
            subscription_name="Spotify",
            billing_date="2026-08-05",
            amount=11.99,
            currency="USD",
            status="PAID",
            price_change_from_previous=0.0
        ),
        BillingHistoryItem(
            subscription_id="sub-3",
            subscription_name="Gold's Gym",
            billing_date="2026-07-28",
            amount=55.00,
            currency="USD",
            status="PAID",
            price_change_from_previous=0.0
        )
    ]

