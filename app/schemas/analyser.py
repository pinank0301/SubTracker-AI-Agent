from typing import List, Optional, Dict
from pydantic import BaseModel, Field
from app.schemas.subscription import SubscriptionDTO, UsageSignal, BillingHistoryItem


class UsageScore(BaseModel):
    """
    Quantitative usage scoring metrics.
    """
    score: float = Field(..., ge=0.0, le=100.0, description="Usage score 0-100")
    tier: str = Field(..., description="HIGH, MODERATE, LOW, NEGLIGIBLE")
    cost_per_active_day: float = Field(default=0.0, description="Normalized cost per active day in past month")
    cost_per_hour: float = Field(default=0.0, description="Normalized cost per hour used")
    efficiency_rating: str = Field(default="GOOD", description="EXCELLENT, GOOD, POOR, WASTEFUL")


class CategoryBenchmark(BaseModel):
    """
    Comparison against industry category averages.
    """
    category: str
    average_market_monthly_spend: float
    user_monthly_spend: float
    delta_percentage: float = Field(..., description="Percentage above (+) or below (-) industry average")
    benchmark_status: str = Field(..., description="BELOW_AVERAGE, AVERAGE, ABOVE_AVERAGE, SIGNIFICANTLY_EXPENSIVE")


class SubscriptionInsightProfile(BaseModel):
    """
    Per-subscription detailed insight profile.
    """
    subscription_id: Optional[str] = None
    subscription_name: str
    category: str
    monthly_cost: float
    annual_cost: float
    currency: str = "USD"
    billing_cycle: str = "MONTHLY"
    usage_metrics: UsageScore
    category_benchmark: Optional[CategoryBenchmark] = None
    is_underutilized: bool = Field(default=False, description="Flag indicating low engagement vs cost")
    is_overpriced: bool = Field(default=False, description="Flag indicating price significantly above market benchmark")
    insight_summary: str = Field(..., description="AI generated analytical summary for this subscription")
    key_findings: List[str] = Field(default_factory=list)
    risk_flags: List[str] = Field(default_factory=list)


class AnalyserReport(BaseModel):
    """
    Aggregated subscription analysis report for the user.
    """
    user_id: Optional[str] = None
    total_monthly_spend: float
    total_annual_spend: float
    currency: str = "USD"
    total_subscriptions_count: int
    active_subscriptions_count: int
    underutilized_subscriptions_count: int
    overpriced_subscriptions_count: int
    spend_by_category: Dict[str, float] = Field(default_factory=dict)
    insights_by_subscription: List[SubscriptionInsightProfile] = Field(default_factory=list)
    overall_portfolio_health: str = Field(
        default="HEALTHY",
        description="EXCELLENT, HEALTHY, NEEDS_ATTENTION, CRITICAL_OVERSPENDING"
    )
    executive_summary: str = Field(..., description="High-level synthesis of user's overall spend and habits")


class AnalyseRequest(BaseModel):
    """
    Input payload for Subscription Analyser Agent.
    """
    user_id: Optional[str] = Field(None, description="User ID to fetch data for if not passing direct lists")
    subscriptions: Optional[List[SubscriptionDTO]] = Field(default=None, description="Direct list of subscriptions")
    usage_signals: Optional[List[UsageSignal]] = Field(default=None, description="Usage telemetries")
    billing_history: Optional[List[BillingHistoryItem]] = Field(default=None, description="Historical transactions")
