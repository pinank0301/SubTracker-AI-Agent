# pyrefly: ignore [missing-import]
import pytest
from app.agents.renewal_agent import RenewalPredictionAgent
from app.schemas.renewal import RenewalRiskLevel


@pytest.mark.asyncio
async def test_renewal_agent_predicts_risk_and_silent_renewals(sample_subscriptions, sample_usage_signals, sample_billing_history):
    agent = RenewalPredictionAgent()

    assessment = await agent.predict_renewals(
        subscriptions=sample_subscriptions,
        usage_signals=sample_usage_signals,
        billing_history=sample_billing_history,
        user_id="user-test-123"
    )


    assert len(assessment.subscription_assessments) == 3
    assert assessment.total_upcoming_30d_renewal_spend > 0

    # Gym assessment should have high churn likelihood and critical/high risk due to dormancy
    gym_assessment = next((a for a in assessment.subscription_assessments if "Gym" in a.subscription_name), None)
    assert gym_assessment is not None
    assert gym_assessment.churn_likelihood_score >= 50.0
    assert gym_assessment.risk_level in [RenewalRiskLevel.CRITICAL, RenewalRiskLevel.HIGH]

    # Netflix assessment should flag market price hike potential
    netflix_assessment = next((a for a in assessment.subscription_assessments if "Netflix" in a.subscription_name), None)
    assert netflix_assessment is not None
    assert netflix_assessment.price_hike is not None
    assert netflix_assessment.price_hike.is_price_hike_likely is True
