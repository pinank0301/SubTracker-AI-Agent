import logging
# pyrefly: ignore [missing-import]
import httpx
from typing import List, Optional, Dict, Any
from app.config import get_settings
from app.schemas.subscription import (
    SubscriptionDTO,
    BillingCycle,
    SubscriptionStatus,
    UsageSignal,
    BillingHistoryItem
)

logger = logging.getLogger(__name__)


class SubscriptionServiceClient:
    """
    Async REST Client for communicating with Spring Boot Subscription Microservice.
    Fetches dynamic user subscription records and executes subscription updates or cancellations.
    """

    def __init__(self):
        self.settings = get_settings()
        self.base_url = self.settings.SUBSCRIPTION_SERVICE_BASE_URL.rstrip("/")
        self.timeout = self.settings.SUBSCRIPTION_SERVICE_TIMEOUT_SECONDS

    async def get_user_subscriptions(
        self,
        user_id: str = "default-user",
        jwt_token: Optional[str] = None
    ) -> List[SubscriptionDTO]:
        """
        Fetches all subscriptions for a user from Spring Boot Subscription Service.
        """
        headers = {
            "X-User-Id": str(user_id),
            "Content-Type": "application/json"
        }
        if jwt_token:
            headers["Authorization"] = f"Bearer {jwt_token}"

        url = f"{self.base_url}/api/subscriptions"

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, headers=headers)
                if response.status_code == 200:
                    payload = response.json()
                    raw_data = payload.get("data", []) if isinstance(payload, dict) else payload
                    subscriptions = []
                    for item in raw_data:
                        subscriptions.append(SubscriptionDTO(
                            id=item.get("id"),
                            userId=item.get("userId", user_id),
                            name=item.get("name", "Unknown"),
                            category=item.get("category", "Other"),
                            amount=float(item.get("amount", 0.0)),
                            currency=item.get("currency", "USD"),
                            billingCycle=BillingCycle(item.get("billingCycle", "MONTHLY")),
                            renewalDate=item.get("renewalDate"),
                            status=SubscriptionStatus(item.get("status", "ACTIVE")),
                            description=item.get("description")
                        ))
                    logger.info("Fetched %d dynamic subscriptions for user %s", len(subscriptions), user_id)
                    return subscriptions
                else:
                    logger.warning(
                        "subscription-service returned HTTP %d: %s",
                        response.status_code,
                        response.text
                    )
        except Exception as e:
            logger.warning("Could not reach subscription-service at %s: %s", url, e)

        return []

    async def cancel_subscription(
        self,
        subscription_id: str,
        user_id: str = "default-user"
    ) -> bool:
        """
        Calls DELETE /api/subscriptions/{id} to cancel a subscription.
        """
        headers = {"X-User-Id": str(user_id)}
        url = f"{self.base_url}/api/subscriptions/{subscription_id}"

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.delete(url, headers=headers)
                return response.status_code in [200, 204]
        except Exception as e:
            logger.error("Failed to cancel subscription %s on subscription-service: %s", subscription_id, e)
            return False

    async def update_subscription_plan(
        self,
        subscription_id: str,
        update_data: Dict[str, Any],
        user_id: str = "default-user"
    ) -> bool:
        """
        Calls PUT /api/subscriptions/{id} to update plan / amount.
        """
        headers = {
            "X-User-Id": str(user_id),
            "Content-Type": "application/json"
        }
        url = f"{self.base_url}/api/subscriptions/{subscription_id}"

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.put(url, json=update_data, headers=headers)
                return response.status_code == 200
        except Exception as e:
            logger.error("Failed to update subscription %s: %s", subscription_id, e)
            return False


_global_sub_client: Optional[SubscriptionServiceClient] = None


def get_subscription_client() -> SubscriptionServiceClient:
    global _global_sub_client
    if _global_sub_client is None:
        _global_sub_client = SubscriptionServiceClient()
    return _global_sub_client
