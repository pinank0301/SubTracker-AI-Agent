from enum import Enum
from typing import List, Optional, Dict, Any
# pyrefly: ignore [missing-import]
from pydantic import BaseModel, Field
from app.schemas.subscription import SubscriptionDTO, UsageSignal


class ActionType(str, Enum):
    CANCEL_SUBSCRIPTION = "CANCEL_SUBSCRIPTION"
    DOWNGRADE_SUBSCRIPTION = "DOWNGRADE_SUBSCRIPTION"
    UPGRADE_SUBSCRIPTION = "UPGRADE_SUBSCRIPTION"
    PAUSE_SUBSCRIPTION = "PAUSE_SUBSCRIPTION"
    SET_RENEWAL_ALERT = "SET_RENEWAL_ALERT"
    SWITCH_ANNUAL_PLAN = "SWITCH_ANNUAL_PLAN"
    EXPLORE_BUNDLE = "EXPLORE_BUNDLE"


class ActionCard(BaseModel):
    """
    Actionable card displayed in UI for direct one-click execution with transparent confirmation support.
    """
    action_id: str
    title: str
    description: str
    action_type: ActionType
    target_subscription_id: Optional[str] = None
    target_subscription_name: str
    payload: Dict[str, Any] = Field(default_factory=dict)
    requires_confirmation: bool = True
    confirmation_title: Optional[str] = None
    confirmation_message: Optional[str] = None
    provider_portal_url: Optional[str] = None
    estimated_monthly_savings: Optional[float] = None
    button_text: str = "Apply Action"


class GuardrailStatus(BaseModel):
    """
    Validation audit trail from LangChain Guardrail layer.
    """
    passed: bool = True
    domain_valid: bool = True
    security_valid: bool = True
    category: str = "SUBSCRIPTION_QUERY"
    rejection_reason: Optional[str] = None


class ChatRequest(BaseModel):
    """
    Payload for conversational chat with the Master Orchestrator Agent.
    """
    message: str = Field(..., min_length=1, description="User question or instruction in natural language")
    user_id: Optional[str] = Field(default="default-user", description="Owner User ID")
    session_id: Optional[str] = Field(default=None, description="Conversation session ID for memory persistence")
    subscriptions: Optional[List[SubscriptionDTO]] = Field(
        default=None,
        description="Optional list of current subscriptions; if omitted, fetched automatically via subscription-service"
    )
    usage_signals: Optional[List[UsageSignal]] = Field(
        default=None,
        description="Optional telemetry usage signals provided by user or frontend"
    )



class WebSearchSource(BaseModel):
    """
    Verified web search citation source or portal link.
    """
    title: str
    url: str
    snippet: Optional[str] = None
    domain: Optional[str] = None


class ChatResponse(BaseModel):
    """
    Synthesized response from the Conversational Master Orchestrator Agent.
    """
    response: str = Field(..., description="Markdown formatted conversational response")
    session_id: str
    intent_detected: str
    agents_invoked: List[str] = Field(default_factory=list)
    action_cards: List[ActionCard] = Field(default_factory=list)
    sources: List[WebSearchSource] = Field(default_factory=list, description="Web search citation links")
    guardrail_status: GuardrailStatus
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class ActionExecutionRequest(BaseModel):
    """
    Request to execute an action (such as cancelling or switching a subscription).
    """
    action_id: str
    action_type: ActionType
    subscription_id: Optional[str] = None
    subscription_name: str
    user_id: Optional[str] = "default-user"
    payload: Dict[str, Any] = Field(default_factory=dict)


class ActionExecutionResponse(BaseModel):
    """
    Result of an executed action.
    """
    action_id: str
    status: str = Field(..., description="SUCCESS, FAILED, PENDING_CONFIRMATION")
    message: str
    data: Optional[Dict[str, Any]] = None
