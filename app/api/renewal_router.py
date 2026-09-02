import logging
# pyrefly: ignore [missing-import]
from fastapi import APIRouter, Depends, HTTPException, status
from app.schemas.common import ApiResponse
from app.schemas.renewal import RenewalPredictionRequest, RenewalRiskAssessment
from app.agents.renewal_agent import RenewalPredictionAgent
from app.agents.tools.subscription_client import get_subscription_client
from app.api.dependencies import get_renewal_agent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/predict-renewals", tags=["Renewal Prediction Agent"])


@router.post("", response_model=ApiResponse[RenewalRiskAssessment])
async def predict_renewals(
    request: RenewalPredictionRequest,
    renewal_agent: RenewalPredictionAgent = Depends(get_renewal_agent)
):
    """
    Direct endpoint for Renewal Prediction Agent.
    Predicts renewal dates, calculates silent auto-renewal risks, forecasts potential price hikes,
    and estimates churn/cancellation likelihood before charges occur.
    """
    try:
        user_id = request.user_id or "default-user"
        sub_client = get_subscription_client()
        subscriptions = request.subscriptions or await sub_client.get_user_subscriptions(user_id=user_id)
        signals = request.usage_signals or []
        history = request.billing_history or []

        assessment = await renewal_agent.predict_renewals(
            subscriptions=subscriptions,
            billing_history=history,
            usage_signals=signals,
            user_id=user_id
        )
        return ApiResponse.ok(data=assessment, message="Renewal risk assessment completed successfully")
    except Exception as e:
        logger.error("Renewal prediction failed: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Renewal Prediction Agent error: {str(e)}"
        )


@router.get("/user/{user_id}", response_model=ApiResponse[RenewalRiskAssessment])
async def predict_user_renewals(
    user_id: str,
    renewal_agent: RenewalPredictionAgent = Depends(get_renewal_agent)
):
    """
    Fetches user subscriptions and predicts upcoming renewal and churn risks.
    """
    try:
        sub_client = get_subscription_client()
        subscriptions = await sub_client.get_user_subscriptions(user_id=user_id)

        assessment = await renewal_agent.predict_renewals(
            subscriptions=subscriptions,
            billing_history=[],
            usage_signals=[],
            user_id=user_id
        )
        return ApiResponse.ok(data=assessment, message=f"Renewal predictions for user {user_id} generated")
    except Exception as e:
        logger.error("Renewal prediction failed for user %s: %s", user_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error predicting renewals for user: {str(e)}"
        )
