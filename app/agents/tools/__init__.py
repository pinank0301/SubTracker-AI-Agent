"""
Agent Tools and External Microservice Connectors Package.
"""
from app.agents.tools.benchmark_data import get_category_benchmark, calculate_dynamic_benchmark
from app.agents.tools.market_plans import (
    get_market_alternatives,
    find_applicable_bundles,
    calculate_annual_discount_plan,
    calculate_tier_downgrade_plan
)
from app.agents.tools.subscription_client import SubscriptionServiceClient, get_subscription_client
from app.agents.tools.web_search_tool import SubscriptionWebSearchTool, get_web_search_tool

__all__ = [
    "get_category_benchmark",
    "calculate_dynamic_benchmark",
    "get_market_alternatives",
    "find_applicable_bundles",
    "calculate_annual_discount_plan",
    "calculate_tier_downgrade_plan",
    "SubscriptionServiceClient",
    "get_subscription_client",
    "SubscriptionWebSearchTool",
    "get_web_search_tool"
]
