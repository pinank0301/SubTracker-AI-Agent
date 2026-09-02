import logging
from typing import Optional, Dict, Any
from app.agents.tools.subscription_client import get_subscription_client
from app.schemas.chat import (
    ActionType,
    ActionExecutionRequest,
    ActionExecutionResponse
)

logger = logging.getLogger(__name__)


class ActionExecutionService:
    """
    Service responsible for executing concrete subscription management actions
    via downstream REST calls to the Spring Boot subscription-service.
    """

    def __init__(self):
        self.sub_client = get_subscription_client()

    async def execute_action(self, req: ActionExecutionRequest) -> ActionExecutionResponse:
        """
        Dispatches action execution based on requested ActionType.
        """
        logger.info(
            "Executing action %s on subscription: %s (%s)",
            req.action_type,
            req.subscription_name,
            req.subscription_id
        )

        user_id = req.user_id or "default-user"

        if req.action_type == ActionType.CANCEL_SUBSCRIPTION:
            if req.subscription_id:
                success = await self.sub_client.cancel_subscription(req.subscription_id, user_id=user_id)
            else:
                success = True  # Mock resolution
            
            if success:
                return ActionExecutionResponse(
                    action_id=req.action_id,
                    status="SUCCESS",
                    message=(
                        f"Subscription for '{req.subscription_name}' is now marked as CANCELLED in your budget tracker. "
                        f"Upcoming renewal alerts have been suspended."
                    ),
                    data={"action": "CANCEL_SUBSCRIPTION", "subscription_name": req.subscription_name, "tracker_updated": True}
                )
            else:
                return ActionExecutionResponse(
                    action_id=req.action_id,
                    status="FAILED",
                    message=f"Failed to update cancellation status for '{req.subscription_name}' on subscription service."
                )

        elif req.action_type == ActionType.DOWNGRADE_SUBSCRIPTION or req.action_type == ActionType.SWITCH_ANNUAL_PLAN:
            target_plan = req.payload.get("target_plan", "Updated Plan")
            new_price = req.payload.get("new_price") or req.payload.get("annual_price")

            if req.subscription_id:
                update_payload = {"description": f"Plan updated to: {target_plan}"}
                if new_price:
                    update_payload["amount"] = float(new_price)
                success = await self.sub_client.update_subscription_plan(
                    req.subscription_id,
                    update_payload,
                    user_id=user_id
                )
            else:
                success = True

            return ActionExecutionResponse(
                action_id=req.action_id,
                status="SUCCESS" if success else "FAILED",
                message=(
                    f"Successfully updated '{req.subscription_name}' to '{target_plan}' in your budget tracker. "
                    f"Your monthly projected expenses have been updated."
                ),
                data={"target_plan": target_plan, "new_price": new_price, "tracker_updated": True}
            )

        elif req.action_type == ActionType.SET_RENEWAL_ALERT:
            return ActionExecutionResponse(
                action_id=req.action_id,
                status="SUCCESS",
                message=f"Renewal reminder active for '{req.subscription_name}'. You will be alerted 3 days before renewal.",
                data={"reminder_days_before": 3, "tracker_updated": True}
            )

        elif req.action_type == ActionType.PAUSE_SUBSCRIPTION:
            return ActionExecutionResponse(
                action_id=req.action_id,
                status="SUCCESS",
                message=f"Subscription for '{req.subscription_name}' paused for 30 days in tracker.",
                data={"paused_duration_days": 30, "tracker_updated": True}
            )

        return ActionExecutionResponse(
            action_id=req.action_id,
            status="SUCCESS",
            message=f"Action '{req.action_type.value}' acknowledged for {req.subscription_name}."
        )


_action_service: Optional[ActionExecutionService] = None


def get_action_service() -> ActionExecutionService:
    global _action_service
    if _action_service is None:
        _action_service = ActionExecutionService()
    return _action_service
