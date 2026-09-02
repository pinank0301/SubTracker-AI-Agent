# pyrefly: ignore [missing-import]
import pytest
from app.agents.analyser_agent import SubscriptionAnalyserAgent
from app.agents.optimizer_agent import SubscriptionOptimizerAgent
from app.schemas.optimizer import OptimizationActionType


@pytest.mark.asyncio
async def test_optimizer_agent_produces_ranked_recommendations(sample_subscriptions, sample_usage_signals):
    analyser = SubscriptionAnalyserAgent()
    optimizer = SubscriptionOptimizerAgent()

    report = await analyser.analyse(
        subscriptions=sample_subscriptions,
        usage_signals=sample_usage_signals,
        user_id="user-test-123"
    )

    optimizations = await optimizer.optimize(
        analyser_report=report,
        subscriptions=sample_subscriptions,
        user_id="user-test-123"
    )

    assert optimizations.recommendations_count > 0
    assert optimizations.total_potential_monthly_savings > 0

    # The top recommendation should be cancelling or pausing the unused Gym membership ($55/mo)
    top_rec = optimizations.recommendations[0]
    assert top_rec.priority_rank == 1
    assert "Gym" in top_rec.subscription_name
    assert top_rec.action_type in [OptimizationActionType.CANCEL, OptimizationActionType.PAUSE]
    assert top_rec.monthly_savings == 55.00
    assert top_rec.annual_savings == round(55.00 * 12.0, 2)


@pytest.mark.asyncio
async def test_web_search_tool_direct():
    from app.agents.tools.web_search_tool import get_web_search_tool
    tool = get_web_search_tool()
    
    # Test searching for Netflix deals
    results = await tool.search_subscription_deals("Netflix", max_results=2)
    # Even if offline/rate-limited, it should return a list without throwing exceptions
    assert isinstance(results, list)
    
    summary = await tool.get_live_deals_summary(["Netflix", "Spotify"])
    assert isinstance(summary, str)


@pytest.mark.asyncio
async def test_optimizer_agent_with_mocked_web_search(sample_subscriptions, sample_usage_signals, mocker):
    from app.agents.tools.web_search_tool import SubscriptionWebSearchTool
    
    # Mock live web search to return a sample deal
    mocker.patch.object(
        SubscriptionWebSearchTool,
        "get_live_deals_summary",
        return_value="### Live Market Insights for Netflix:\n- **Netflix Standard with Ads**: Available for $6.99/mo (Source: https://netflix.com)"
    )

    analyser = SubscriptionAnalyserAgent()
    optimizer = SubscriptionOptimizerAgent()

    report = await analyser.analyse(
        subscriptions=sample_subscriptions,
        usage_signals=sample_usage_signals,
        user_id="user-test-123"
    )

    optimizations = await optimizer.optimize(
        analyser_report=report,
        subscriptions=sample_subscriptions,
        user_id="user-test-123"
    )

    assert optimizations.recommendations_count > 0
    assert optimizations.strategic_summary is not None
    assert len(optimizations.strategic_summary) > 0
