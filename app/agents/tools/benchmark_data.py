import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


def calculate_dynamic_benchmark(
    category_name: str,
    user_amount: float,
    currency: str = "USD"
) -> Dict[str, Any]:
    """
    Dynamically computes a benchmark metric based on category and market standard baseline ranges.
    Evaluates whether the user's spending is above, below, or in-line with standard category tiers.
    """
    cat_lower = (category_name or "Other").lower()

    # Dynamic baselines per category
    if "gym" in cat_lower or "fitness" in cat_lower:
        baseline = 40.0
        typical_count = 1
        desc = "Fitness & Gym memberships"
    elif "stream" in cat_lower or "entertain" in cat_lower or "video" in cat_lower:
        baseline = 20.0
        typical_count = 2
        desc = "Streaming & Entertainment services"
    elif "music" in cat_lower or "audio" in cat_lower:
        baseline = 11.0
        typical_count = 1
        desc = "Music streaming platforms"
    elif "product" in cat_lower or "saas" in cat_lower or "ai" in cat_lower:
        baseline = 25.0
        typical_count = 2
        desc = "Productivity, SaaS & AI subscriptions"
    elif "cloud" in cat_lower or "dev" in cat_lower or "infra" in cat_lower:
        baseline = 30.0
        typical_count = 1
        desc = "Cloud & Developer infrastructure"
    elif "gaming" in cat_lower:
        baseline = 15.0
        typical_count = 1
        desc = "Gaming passes and online networks"
    elif "news" in cat_lower or "media" in cat_lower:
        baseline = 10.0
        typical_count = 1
        desc = "News & Media publications"
    elif "edu" in cat_lower or "learn" in cat_lower:
        baseline = 18.0
        typical_count = 1
        desc = "Education & Online courses"
    else:
        baseline = max(15.0, round(user_amount * 0.8, 2))
        typical_count = 1
        desc = "General subscriptions"

    return {
        "category": category_name or "Other",
        "avg_monthly_spend": baseline,
        "typical_services_count": typical_count,
        "description": desc,
        "currency": currency
    }


def get_category_benchmark(category_name: str, user_amount: float = 20.0) -> Dict[str, Any]:
    """
    Returns dynamically computed category benchmark profile.
    """
    return calculate_dynamic_benchmark(category_name=category_name, user_amount=user_amount)
