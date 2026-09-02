import pytest
from app.agents.analyser_agent import SubscriptionAnalyserAgent
from app.schemas.subscription import SubscriptionDTO, BillingCycle, SubscriptionStatus, UsageSignal


@pytest.mark.asyncio
async def test_analyser_agent_identifies_underutilization(sample_subscriptions, sample_usage_signals):
    agent = SubscriptionAnalyserAgent()

    report = await agent.analyse(
        subscriptions=sample_subscriptions,
        usage_signals=sample_usage_signals,
        user_id="user-test-123"
    )

    assert report.total_subscriptions_count == 3
    assert report.active_subscriptions_count == 3
    assert report.total_monthly_spend == round(22.99 + 11.99 + 55.00, 2)
    assert report.underutilized_subscriptions_count >= 1

    # Check gym is flagged underutilized
    gym_profile = next((p for p in report.insights_by_subscription if "Gym" in p.subscription_name), None)
    assert gym_profile is not None
    assert gym_profile.is_underutilized is True
    assert gym_profile.usage_metrics.score < 35.0

    # Check Spotify has high usage
    spotify_profile = next((p for p in report.insights_by_subscription if "Spotify" in p.subscription_name), None)
    assert spotify_profile is not None
    assert spotify_profile.is_underutilized is False
    assert spotify_profile.usage_metrics.score >= 70.0


def test_usage_score_calculation(sample_subscriptions, sample_usage_signals):
    agent = SubscriptionAnalyserAgent()
    gym_sub = sample_subscriptions[2]
    gym_signal = sample_usage_signals[2]

    score = agent.calculate_usage_score(gym_sub, gym_signal)
    assert score.score < 25.0
    assert score.efficiency_rating in ["POOR", "WASTEFUL"]
    assert score.cost_per_active_day >= 50.0  # $55 / 1 day
