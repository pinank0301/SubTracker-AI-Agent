from enum import Enum
from typing import Optional, List
from pydantic import BaseModel, Field
from datetime import date


class BillingCycle(str, Enum):
    MONTHLY = "MONTHLY"
    ANNUALLY = "ANNUALLY"
    QUARTERLY = "QUARTERLY"
    WEEKLY = "WEEKLY"


class SubscriptionStatus(str, Enum):
    ACTIVE = "ACTIVE"
    CANCELLED = "CANCELLED"
    PAUSED = "PAUSED"
    EXPIRED = "EXPIRED"


class SubscriptionCategory(str, Enum):
    ENTERTAINMENT = "Entertainment"
    STREAMING = "Streaming"
    MUSIC = "Music"
    PRODUCTIVITY = "Productivity"
    FITNESS = "Fitness"
    CLOUD = "Cloud & Dev"
    GAMING = "Gaming"
    NEWS_MEDIA = "News & Media"
    EDUCATION = "Education"
    OTHER = "Other"


class SubscriptionDTO(BaseModel):
    """
    Data Transfer Object mirroring Spring Boot's Subscription entity/response.
    """
    id: Optional[str] = Field(None, description="Subscription UUID")
    userId: Optional[str] = Field(None, description="User UUID")
    name: str = Field(..., description="Service name (e.g. Netflix, Spotify, AWS)")
    category: str = Field(default="Other", description="Category (Entertainment, Fitness, etc.)")
    amount: float = Field(..., ge=0.0, description="Cost per cycle")
    currency: str = Field(default="USD", max_length=10, description="Currency code (USD, EUR, etc.)")
    billingCycle: BillingCycle = Field(default=BillingCycle.MONTHLY, description="Billing period")
    renewalDate: Optional[str] = Field(None, description="Next renewal date in YYYY-MM-DD")
    status: SubscriptionStatus = Field(default=SubscriptionStatus.ACTIVE, description="Status")
    description: Optional[str] = Field(None, description="Optional notes or tier description")

    @property
    def monthly_cost(self) -> float:
        """Normalized monthly cost helper."""
        if self.billingCycle == BillingCycle.ANNUALLY:
            return round(self.amount / 12.0, 2)
        elif self.billingCycle == BillingCycle.QUARTERLY:
            return round(self.amount / 3.0, 2)
        elif self.billingCycle == BillingCycle.WEEKLY:
            return round(self.amount * 4.33, 2)
        return round(self.amount, 2)

    @property
    def annual_cost(self) -> float:
        """Normalized annual cost helper."""
        return round(self.monthly_cost * 12.0, 2)


class UsageSignal(BaseModel):
    """
    Telemetry and behavioral signals for a subscription.
    """
    subscription_id: Optional[str] = None
    subscription_name: str
    active_days_last_30: int = Field(default=0, ge=0, le=30, description="Number of days active in past 30 days")
    hours_used_last_30: float = Field(default=0.0, ge=0.0, description="Total hours consumed/engaged in past 30 days")
    logins_last_30: int = Field(default=0, ge=0, description="Login or session count")
    last_active_date: Optional[str] = Field(None, description="Last detected usage date (YYYY-MM-DD)")
    features_used_ratio: float = Field(default=0.5, ge=0.0, le=1.0, description="Ratio of plan features actually used")
    engagement_trend: str = Field(
        default="STABLE",
        description="Engagement trajectory: INCREASING, STABLE, DECLINING, DORMANT"
    )


class BillingHistoryItem(BaseModel):
    """
    Past billing transaction.
    """
    subscription_id: Optional[str] = None
    subscription_name: str
    billing_date: str = Field(..., description="Transaction date (YYYY-MM-DD)")
    amount: float = Field(..., ge=0.0)
    currency: str = Field(default="USD")
    status: str = Field(default="PAID", description="PAID, REFUNDED, FAILED")
    price_change_from_previous: Optional[float] = Field(default=0.0, description="Percentage change from previous cycle")
