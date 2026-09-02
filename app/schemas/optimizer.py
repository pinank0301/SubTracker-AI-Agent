from enum import Enum
from typing import List, Optional, Dict, Any
# pyrefly: ignore [missing-import]
from pydantic import BaseModel, Field
from app.schemas.subscription import SubscriptionDTO
from app.schemas.analyser import AnalyserReport
from app.schemas.chat import ActionCard


class OptimizationActionType(str, Enum):
    CANCEL = "CANCEL"
    DOWNGRADE_TIER = "DOWNGRADE_TIER"
    SWITCH_ANNUAL = "SWITCH_ANNUAL"
    BUNDLE_DEAL = "BUNDLE_DEAL"
    SWITCH_PROVIDER = "SWITCH_PROVIDER"
    PAUSE = "PAUSE"
    APPLY_DISCOUNT = "APPLY_DISCOUNT"


class OptimizationRecommendation(BaseModel):
    """
    Actionable recommendation produced by the Optimizer Agent.
    """
    id: str = Field(..., description="Unique recommendation ID")
    subscription_name: str
    subscription_id: Optional[str] = None
    action_type: OptimizationActionType
    current_cost_monthly: float
    new_estimated_cost_monthly: float
    monthly_savings: float = Field(..., description="Estimated monthly savings")
    annual_savings: float = Field(..., description="Estimated annual savings")
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="Confidence in recommendation (0-1)")
    priority_rank: int = Field(..., ge=1, description="Ranking priority (1 = highest savings/impact)")
    title: str = Field(..., description="Catchy title (e.g. 'Downgrade Netflix to Standard with Ads')")
    rationale: str = Field(..., description="Analytical reasoning based on user usage data and market options")
    suggested_target_plan: Optional[str] = Field(None, description="Recommended alternative plan or bundle")
    action_payload: Dict[str, Any] = Field(
        default_factory=dict,
        description="Structured data payload required to execute this action via backend API"
    )


class RankedOptimizations(BaseModel):
    """
    Ranked optimization suite.
    """
    user_id: Optional[str] = None
    total_potential_monthly_savings: float
    total_potential_annual_savings: float
    currency: str = "USD"
    recommendations_count: int
    recommendations: List[OptimizationRecommendation] = Field(default_factory=list)
    action_cards: List[ActionCard] = Field(default_factory=list)
    strategic_summary: str = Field(..., description="Overview of the savings strategy")


class OptimizeRequest(BaseModel):
    """
    Input payload for Subscription Optimizer Agent.
    """
    user_id: Optional[str] = None
    analyser_report: Optional[AnalyserReport] = None
    subscriptions: Optional[List[SubscriptionDTO]] = None
