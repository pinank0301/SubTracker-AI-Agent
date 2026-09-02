import logging
# pyrefly: ignore [missing-import]
from fastapi import APIRouter, Depends, HTTPException, status
from app.schemas.common import ApiResponse
from app.schemas.optimizer import OptimizeRequest, RankedOptimizations
from app.agents.analyser_agent import SubscriptionAnalyserAgent
from app.agents.optimizer_agent import SubscriptionOptimizerAgent
from app.agents.tools.subscription_client import get_subscription_client
from app.api.dependencies import get_analyser, get_optimizer

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/optimize", tags=["Subscription Optimizer Agent"])


@router.post("", response_model=ApiResponse[RankedOptimizations])
async def optimize_subscriptions(
    request: OptimizeRequest,
    analyser: SubscriptionAnalyserAgent = Depends(get_analyser),
    optimizer: SubscriptionOptimizerAgent = Depends(get_optimizer)
):
    """
    Direct endpoint for Subscription Optimizer Agent.
    Evaluates subscriptions against market catalogs, tier alternatives, bundling deals,
    and underutilization to generate ranked cost-saving recommendations.
    """
    try:
        user_id = request.user_id or "default-user"
        analyser_report = request.analyser_report

        if not analyser_report:
            sub_client = get_subscription_client()
            subs = request.subscriptions or await sub_client.get_user_subscriptions(user_id=user_id)
            analyser_report = await analyser.analyse(subs, usage_signals=[], billing_history=[], user_id=user_id)

        optimizations = await optimizer.optimize(
            analyser_report=analyser_report,
            subscriptions=request.subscriptions,
            user_id=user_id
        )
        return ApiResponse.ok(data=optimizations, message="Optimization recommendations generated successfully")
    except Exception as e:
        logger.error("Optimization failed: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Subscription Optimizer Agent error: {str(e)}"
        )


@router.get("/user/{user_id}", response_model=ApiResponse[RankedOptimizations])
async def optimize_user_subscriptions(
    user_id: str,
    analyser: SubscriptionAnalyserAgent = Depends(get_analyser),
    optimizer: SubscriptionOptimizerAgent = Depends(get_optimizer)
):
    """
    Runs full pipeline (Analysis -> Optimization) for a specific user.
    """
    try:
        sub_client = get_subscription_client()
        subs = await sub_client.get_user_subscriptions(user_id=user_id)

        analyser_report = await analyser.analyse(subs, usage_signals=[], billing_history=[], user_id=user_id)
        optimizations = await optimizer.optimize(
            analyser_report=analyser_report,
            subscriptions=subs,
            user_id=user_id
        )
        return ApiResponse.ok(data=optimizations, message=f"Optimizations for user {user_id} generated")
    except Exception as e:
        logger.error("Optimization failed for user %s: %s", user_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating optimizations for user: {str(e)}"
        )
