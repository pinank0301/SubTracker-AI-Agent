import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


def calculate_annual_discount_plan(service_name: str, monthly_cost: float) -> Optional[Dict[str, Any]]:
    """
    Dynamically computes standard market annual discount (typically 15-20% savings / 2 months free)
    for any given subscription.
    """
    if monthly_cost <= 5.0:
        return None
    # Standard 16.7% annual billing discount (pay for 10 months, get 12)
    discounted_annual_total = round(monthly_cost * 10.0, 2)
    effective_monthly = round(discounted_annual_total / 12.0, 2)
    monthly_savings = round(monthly_cost - effective_monthly, 2)
    annual_savings = round(monthly_cost * 12.0 - discounted_annual_total, 2)

    return {
        "type": "SWITCH_ANNUAL",
        "tier": f"{service_name} Annual Billing",
        "new_monthly_price": effective_monthly,
        "annual_price": discounted_annual_total,
        "monthly_savings": monthly_savings,
        "annual_savings": annual_savings,
        "features": f"Switch to annual billing to save ~17% (₹{annual_savings:.2f}/year)"
    }


def calculate_tier_downgrade_plan(service_name: str, current_cost: float) -> Optional[Dict[str, Any]]:
    """
    Dynamically computes an ad-supported or entry-level tier alternative (typically ~40-50% cheaper)
    for higher-cost subscriptions.
    """
    if current_cost <= 100.0:
        return None

    # Estimate standard lower tier / ad-supported tier
    new_price = round(max(149.0, current_cost * 0.55), 2)
    monthly_savings = round(current_cost - new_price, 2)
    annual_savings = round(monthly_savings * 12.0, 2)

    return {
        "type": "DOWNGRADE_TIER",
        "tier": f"{service_name} Basic / Standard Tier",
        "new_monthly_price": new_price,
        "monthly_savings": monthly_savings,
        "annual_savings": annual_savings,
        "features": f"Downgrade to Standard/Ad-supported plan saving ₹{monthly_savings:.2f}/mo"
    }


def get_market_alternatives(service_name: str, current_cost: float) -> List[Dict[str, Any]]:
    """
    Dynamically generates alternative tier options and annual discount options for any given service.
    """
    alternatives = []
    
    # 1. Tier downgrade option if costly
    downgrade = calculate_tier_downgrade_plan(service_name, current_cost)
    if downgrade:
        alternatives.append(downgrade)

    # 2. Annual billing switch option
    annual_opt = calculate_annual_discount_plan(service_name, current_cost)
    if annual_opt:
        alternatives.append(annual_opt)

    return alternatives


def find_applicable_bundles(service_names: List[str]) -> List[Dict[str, Any]]:
    """
    Dynamically detects opportunities where 2 or more related user subscriptions
    can be bundled together to save money.
    """
    names_lower = [s.lower().strip() for s in service_names]
    bundles = []

    # Dynamic detection for Streaming combinations (e.g. Disney + Hulu / Max)
    has_disney = any("disney" in s for s in names_lower)
    has_hulu = any("hulu" in s for s in names_lower)
    if has_disney and has_hulu:
        bundles.append({
            "bundle_name": "Disney+ Hotstar & Streaming Duo Bundle",
            "matched_services": ["Disney+", "Hulu"],
            "bundle_monthly_price": 499.00,
            "potential_monthly_savings": 250.00,
            "potential_annual_savings": 3000.00,
            "description": "Combine standalone streaming subscriptions into a Duo bundle to save monthly."
        })

    # Dynamic detection for Apple ecosystem (Music + TV / iCloud)
    has_apple_music = any("apple music" in s or "itunes" in s for s in names_lower)
    has_icloud = any("icloud" in s or "apple tv" in s for s in names_lower)
    if has_apple_music and has_icloud:
        bundles.append({
            "bundle_name": "Apple One Individual Bundle",
            "matched_services": ["Apple Music", "iCloud / Apple TV+"],
            "bundle_monthly_price": 195.00,
            "potential_monthly_savings": 115.00,
            "potential_annual_savings": 1380.00,
            "description": "Consolidate Apple Music and iCloud/media services into Apple One."
        })

    return bundles


PROVIDER_PORTALS = {
    "netflix": "https://www.netflix.com/youraccount",
    "spotify": "https://www.spotify.com/account/overview/",
    "disney": "https://www.disneyplus.com/account",
    "hulu": "https://secure.hulu.com/account",
    "apple": "https://account.apple.com/subscriptions",
    "itunes": "https://account.apple.com/subscriptions",
    "icloud": "https://account.apple.com/subscriptions",
    "amazon": "https://www.amazon.com/mc/manage",
    "prime": "https://www.amazon.com/mc/manage",
    "youtube": "https://www.youtube.com/paid_memberships",
    "google": "https://play.google.com/store/account/subscriptions",
    "microsoft": "https://account.microsoft.com/services",
    "office": "https://account.microsoft.com/services",
    "github": "https://github.com/settings/billing",
    "chatgpt": "https://chatgpt.com/#settings/Subscription",
    "openai": "https://platform.openai.com/account/billing"
}


def get_provider_portal_url(service_name: str) -> Optional[str]:
    """
    Returns the direct official web portal URL for managing or cancelling a subscription.
    """
    if not service_name:
        return None
    name_lower = service_name.lower().strip()
    for key, url in PROVIDER_PORTALS.items():
        if key in name_lower:
            return url
    return None
