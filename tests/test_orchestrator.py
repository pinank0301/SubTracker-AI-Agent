import pytest
from app.agents.orchestrator import ConversationalOrchestratorAgent
from app.schemas.chat import ChatRequest


@pytest.mark.asyncio
async def test_orchestrator_in_domain_chat(sample_subscriptions):
    orchestrator = ConversationalOrchestratorAgent()

    req = ChatRequest(
        message="How much do I spend on streaming and fitness subscriptions each month?",
        user_id="user-test-123",
        session_id="test-session-001",
        subscriptions=sample_subscriptions
    )

    response = await orchestrator.process_chat(req)

    assert response.guardrail_status.passed is True
    assert response.guardrail_status.domain_valid is True
    assert len(response.response) > 0
    assert len(response.agents_invoked) > 0
    assert "Subscription Analyser Agent" in response.agents_invoked


@pytest.mark.asyncio
async def test_orchestrator_action_generation_on_cancel_query(sample_subscriptions):
    orchestrator = ConversationalOrchestratorAgent()

    req = ChatRequest(
        message="Cancel my unused gym plan",
        user_id="user-test-123",
        session_id="test-session-002",
        subscriptions=sample_subscriptions
    )

    response = await orchestrator.process_chat(req)

    assert response.guardrail_status.passed is True
    assert len(response.action_cards) >= 1
    # Check that at least one action card targets the gym
    gym_card = next((c for c in response.action_cards if "Gym" in c.target_subscription_name), None)
    assert gym_card is not None
    assert gym_card.action_type.value == "CANCEL_SUBSCRIPTION"


@pytest.mark.asyncio
async def test_orchestrator_rejects_out_of_domain():
    orchestrator = ConversationalOrchestratorAgent()

    req = ChatRequest(
        message="What is the distance between Earth and Mars?",
        user_id="user-test-123",
        session_id="test-session-003"
    )

    response = await orchestrator.process_chat(req)

    assert response.guardrail_status.passed is False
    assert response.guardrail_status.domain_valid is False
    assert "Subscription & Billing AI Assistant" in response.response
