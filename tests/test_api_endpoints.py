# pyrefly: ignore [missing-import]
import pytest
# pyrefly: ignore [missing-import]
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_endpoint():
    # Test minimal external uptime ping
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

    # Test detailed internal health check
    detailed = client.get("/api/ai/health")
    assert detailed.status_code == 200
    data = detailed.json()
    assert data["success"] is True
    assert data["data"]["status"] == "UP"


def test_chat_endpoint_in_domain(sample_subscriptions):
    payload = {
        "message": "What is my total monthly spend on subscriptions?",
        "user_id": "test-user-456",
        "subscriptions": [s.model_dump() for s in sample_subscriptions]
    }
    response = client.post("/api/ai/chat", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "response" in data["data"]
    assert data["data"]["guardrail_status"]["passed"] is True


def test_chat_endpoint_out_of_domain():
    payload = {
        "message": "Write a python script to calculate fibonacci series",
        "user_id": "test-user-456"
    }
    response = client.post("/api/ai/chat", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["guardrail_status"]["domain_valid"] is False


def test_direct_analyse_endpoint(sample_subscriptions, sample_usage_signals):
    payload = {
        "user_id": "test-user-456",
        "subscriptions": [s.model_dump() for s in sample_subscriptions],
        "usage_signals": [u.model_dump() for u in sample_usage_signals]
    }
    response = client.post("/api/ai/analyse", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "total_monthly_spend" in data["data"]
    assert len(data["data"]["insights_by_subscription"]) == 3


def test_direct_optimize_endpoint(sample_subscriptions, sample_usage_signals):
    payload = {
        "user_id": "test-user-456",
        "subscriptions": [s.model_dump() for s in sample_subscriptions]
    }
    response = client.post("/api/ai/optimize", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "total_potential_monthly_savings" in data["data"]


def test_direct_predict_renewals_endpoint(sample_subscriptions, sample_usage_signals, sample_billing_history):
    payload = {
        "user_id": "test-user-456",
        "subscriptions": [s.model_dump() for s in sample_subscriptions],
        "usage_signals": [u.model_dump() for u in sample_usage_signals],
        "billing_history": [b.model_dump() for b in sample_billing_history]
    }
    response = client.post("/api/ai/predict-renewals", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "subscription_assessments" in data["data"]
    assert len(data["data"]["subscription_assessments"]) == 3
