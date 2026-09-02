# Multi-Agent Subscription AI Service (FastAPI + LangChain)

Enterprise Multi-Agent AI microservice for intelligent subscription management, spend analytics, plan optimization, and renewal forecasting.

---

## 🏛️ Architecture Overview

The system uses a **Hierarchical Multi-Agent Supervisor Architecture** where the **Conversational Subscription Agent acts as the Master Orchestrator**, coordinating 3 specialized worker agents through LangChain and Advanced Guardrails.

```
                  ┌─────────────────────────────────────────┐
                  │    API Gateway / Frontend / Client      │
                  └────────────────────┬────────────────────┘
                                       │ POST /api/ai/chat
                                       ▼
                  ┌─────────────────────────────────────────┐
                  │      LangChain Advanced Guardrails      │
                  │   - Domain Boundary (Subscription Scope)│
                  │   - Anti-Injection & Security Defense   │
                  └────────────────────┬────────────────────┘
                                       │
                                       ▼
                  ┌─────────────────────────────────────────┐
                  │   Conversational Master Orchestrator    │
                  │        (app/agents/orchestrator.py)     │
                  │   - Session Memory Management           │
                  │   - Intent Classification               │
                  │   - Dynamic Multi-Agent Delegation      │
                  │   - Action Triggering & UI Cards        │
                  └───────┬────────────┼────────────┬───────┘
                          │            │            │
           ┌──────────────┘            │            └──────────────┐
           ▼                           ▼                           ▼
┌──────────────────────┐   ┌──────────────────────┐   ┌──────────────────────┐
│Subscription Analyser │   │Subscription Optimizer│   │  Renewal Prediction  │
│        Agent         │   │        Agent         │   │        Agent         │
│ (app/agents/analyser)│   │(app/agents/optimizer)│   │ (app/agents/renewal) │
│ - Usage telemetry    │   │ - Plan alternatives  │   │ - Silent auto-renew  │
│ - Cost-per-use       │   │ - Tier downgrades    │   │ - Price hike alerts  │
│ - Category benchmarks│   │ - Bundling deals     │   │ - Churn risk scoring │
└──────────────────────┘   └──────────────────────┘   └──────────────────────┘
           │                           │                           │
           └───────────────────────────┼───────────────────────────┘
                                       ▼
                  ┌─────────────────────────────────────────┐
                  │   Core Microservice REST Integration    │
                  │  Spring Boot (subscription-service)     │
                  └─────────────────────────────────────────┘
```

---

## 🤖 The 4 Agents & Responsibilities

| Agent | Responsibility | Key Inputs | Key Outputs |
|---|---|---|---|
| **Conversational Master Orchestrator** | Natural language interface, session memory, guardrail enforcement, intent routing, multi-agent synthesis, and action dispatching. | User query, history, agent outputs | Synthesized response, action cards, execution triggers |
| **Subscription Analyser Agent** | Analyses usage frequency, spend metrics, and category benchmarks to build per-user insight profiles. | Subscriptions, usage signals, billing history | Usage scores, cost-per-use, underutilization flags, category benchmarks |
| **Subscription Optimizer Agent** | Recommends downgrades, switches, bundling, or cancellations for under-used or overpriced subscriptions. | Analyser report, market plan catalog, bundle catalog | Ranked optimization recommendations with projected monthly/annual savings |
| **Renewal Prediction Agent** | Predicts upcoming renewals, detects silent auto-renewals, forecasts price hikes, and estimates churn/cancellation likelihood. | Billing history, renewal cycles, user activity signals | Renewal risk score (0-100), predicted next renewal date/amount, price hike alert |

---

## 🛡️ LangChain Advanced Guardrails

1. **Domain Boundary Guardrail (`app/agents/guardrails/domain_guardrail.py`)**:
   - Strictly enforces that queries relate to subscription management, billing, streaming, SaaS, gym, cloud services, and platform capabilities.
   - Out-of-domain queries (e.g. general coding, trivia, sports, weather) are politely rejected with suggested subscription queries.
2. **Security Guardrail (`app/agents/guardrails/security_guardrail.py`)**:
   - Detects and intercepts prompt injection attempts, system prompt extraction, and jailbreak instructions (e.g., "ignore previous instructions", "DAN mode").

---

## 🚀 Getting Started

### 1. Prerequisites
- Python 3.10+ installed

### 2. Create Virtual Environment and Install Dependencies
```bash
# Navigate to service folder
cd ai-agent-service

# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows (PowerShell):
.\venv\Scripts\Activate.ps1
# On Windows (cmd):
.\venv\Scripts\activate.bat
# On Linux/macOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Configure Environment (`.env`)
The `.env` file is pre-configured with the Capgemini Generative AI Engine:
```properties
OPENAI_API_BASE=https://openai.generative-eu.engine.capgemini.com
OPENAI_API_KEY=rjv3v6cX5iaSPpdObI4qG5JU9ITSwNFH6CJpia1g
OPENAI_MODEL_NAME=gemini-3.5-flash
APP_PORT=8000
SUBSCRIPTION_SERVICE_BASE_URL=http://localhost:8082
USE_MOCK_FALLBACK_IF_SERVICE_OFFLINE=true
GUARDRAIL_STRICT_DOMAIN_MODE=true
```

### 4. Run the FastAPI Application
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
Interactive Swagger API documentation will be available at:
👉 **`http://localhost:8000/docs`**

---

## 🧪 Running Automated Tests

Run the complete test suite using pytest:
```bash
pytest
```

---

## 📡 API Endpoints

### 1. Conversational Chat & Orchestration
`POST /api/ai/chat`
```json
{
  "message": "How much do I spend on streaming subscriptions each month and how can I optimize them?",
  "user_id": "user-123",
  "session_id": "session-abc"
}
```

### 2. Execute Action Card
`POST /api/ai/chat/actions/execute`
```json
{
  "action_id": "rec-cancel-123",
  "action_type": "CANCEL_SUBSCRIPTION",
  "subscription_name": "Gold's Gym Membership",
  "subscription_id": "sub-003-gym"
}
```

### 3. Direct Analyser Agent
`GET /api/ai/analyse/user/{user_id}` or `POST /api/ai/analyse`

### 4. Direct Optimizer Agent
`GET /api/ai/optimize/user/{user_id}` or `POST /api/ai/optimize`

### 5. Direct Renewal Prediction Agent
`GET /api/ai/predict-renewals/user/{user_id}` or `POST /api/ai/predict-renewals`

---

## 🌐 Spring Cloud Gateway Route Configuration
To route requests from your Spring Cloud `api-gateway` to this Python AI service, add the following to `api-gateway/src/main/resources/application.properties`:
```properties
spring.cloud.gateway.routes[4].id=ai-agent-service
spring.cloud.gateway.routes[4].uri=http://localhost:8000
spring.cloud.gateway.routes[4].predicates[0]=Path=/api/ai/**
spring.cloud.gateway.routes[4].filters[0].name=CorrelationIdFilter
```
