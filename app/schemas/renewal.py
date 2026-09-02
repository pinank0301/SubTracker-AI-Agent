from enum import Enum
from typing import List, Optional
# pyrefly: ignore [missing-import]
from pydantic import BaseModel, Field
from app.schemas.subscription import SubscriptionDTO, BillingHistoryItem, UsageSignal


class RenewalRiskLevel(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class PriceHikePrediction(BaseModel):
    """
    Price increase forecast for a service.
    """
    subscription_name: str
    is_price_hike_likely: bool = False
    estimated_hike_percentage: float = 0.0
    estimated_new_amount: float = 0.0
    confidence: float = Field(default=0.7, ge=0.0, le=1.0)
    market_signals: List[str] = Field(default_factory=list)


class SubscriptionRenewalRisk(BaseModel):
    """
    Renewal and churn risk assessment for a single subscription.
    """
    subscription_id: Optional[str] = None
    subscription_name: str
    category: str
    current_amount: float
    billing_cycle: str
    predicted_renewal_date: str
    predicted_renewal_amount: float
    days_until_renewal: int
    is_silent_auto_renewal: bool = Field(
        default=False,
        description="True if annual/long-term without active reminders or low engagement"
    )
    churn_likelihood_score: float = Field(
        ..., ge=0.0, le=100.0,
        description="Estimated probability (0-100) that user will want to cancel"
    )
    renewal_risk_score: float = Field(
        ..., ge=0.0, le=100.0,
        description="Overall risk score (0-100) factoring in unwanted spend and silent renewals"
    )
    risk_level: RenewalRiskLevel
    price_hike: Optional[PriceHikePrediction] = None
    risk_factors: List[str] = Field(default_factory=list)
    proactive_suggestion: str = Field(..., description="Actionable suggestion before renewal occurs")


class RenewalRiskAssessment(BaseModel):
    """
    Aggregated renewal prediction report across all user subscriptions.
    """
    user_id: Optional[str] = None
    total_upcoming_30d_renewal_spend: float
    urgent_renewals_count: int
    high_risk_renewals_count: int
    potential_unwanted_renewal_spend: float
    subscription_assessments: List[SubscriptionRenewalRisk] = Field(default_factory=list)
    urgent_action_required: bool = False
    executive_summary: str = Field(..., description="Summary of renewal risks and proactive alerts")


class RenewalPredictionRequest(BaseModel):
    """
    Input payload for Renewal Prediction Agent.
    """
    user_id: Optional[str] = None
    subscriptions: Optional[List[SubscriptionDTO]] = None
    billing_history: Optional[List[BillingHistoryItem]] = None
    usage_signals: Optional[List[UsageSignal]] = None
