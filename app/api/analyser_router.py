import logging
# pyrefly: ignore [missing-import]
from fastapi import APIRouter, Depends, Header, HTTPException, status
from typing import Optional
from app.schemas.common import ApiResponse
from app.schemas.analyser import AnalyseRequest, AnalyserReport
from app.agents.analyser_agent import SubscriptionAnalyserAgent
from app.agents.tools.subscription_client import get_subscription_client
from app.api.dependencies import get_analyser

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/analyse", tags=["Subscription Analyser Agent"])


@router.post("", response_model=ApiResponse[AnalyserReport])
async def analyse_subscriptions(
    request: AnalyseRequest,
    analyser: SubscriptionAnalyserAgent = Depends(get_analyser)
):
    """
    Direct endpoint for Subscription Analyser Agent.
    Analyses usage frequency, cost per use, and category benchmarks to build
    per-subscription insight profiles and identify underutilized plans.
    """
    try:
        subscriptions = request.subscriptions
        user_id = request.user_id or "default-user"
        sub_client = get_subscription_client()

        if not subscriptions:
            subscriptions = await sub_client.get_user_subscriptions(user_id=user_id)

        usage_signals = request.usage_signals or []
        billing_history = request.billing_history or []

        report = await analyser.analyse(
            subscriptions=subscriptions,
            usage_signals=usage_signals,
            billing_history=billing_history,
            user_id=user_id
        )
        return ApiResponse.ok(data=report, message="Subscription analysis completed successfully")
    except Exception as e:
        logger.error("Analysis failed: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Subscription Analyser Agent error: {str(e)}"
        )


@router.get("/user/{user_id}", response_model=ApiResponse[AnalyserReport])
async def analyse_user_subscriptions(
    user_id: str,
    analyser: SubscriptionAnalyserAgent = Depends(get_analyser)
):
    """
    Fetches user subscriptions from core service and produces an analytical insight report.
    """
    try:
        sub_client = get_subscription_client()
        subscriptions = await sub_client.get_user_subscriptions(user_id=user_id)

        report = await analyser.analyse(
            subscriptions=subscriptions,
            usage_signals=[],
            billing_history=[],
            user_id=user_id
        )
        return ApiResponse.ok(data=report, message=f"Analysis for user {user_id} completed")
    except Exception as e:
        logger.error("Analysis failed for user %s: %s", user_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error analyzing user subscriptions: {str(e)}"
        )
