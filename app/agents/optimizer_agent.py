import logging
import uuid
from typing import List, Optional, Any
# pyrefly: ignore [missing-import]
from langchain_core.prompts import ChatPromptTemplate
from app.agents.llm.client import get_chat_llm
from app.agents.tools.market_plans import get_market_alternatives, find_applicable_bundles
from app.agents.tools.web_search_tool import get_web_search_tool
from app.schemas.subscription import SubscriptionDTO
from app.schemas.analyser import AnalyserReport
from app.schemas.chat import ActionCard, ActionType
from app.schemas.optimizer import (
    OptimizationActionType,
    OptimizationRecommendation,
    RankedOptimizations
)

logger = logging.getLogger(__name__)


class SubscriptionOptimizerAgent:
    """
    Subscription Optimizer Agent:
    Evaluates under-used, dormant, or overpriced subscriptions and cross-references
    with market catalogs, tier alternatives, annual discounts, bundling deals,
    and real-time live web search results to generate prioritized cost-saving recommendations.
    """

    def __init__(self):
        self.llm = get_chat_llm(temperature=0.2)
        self.web_search = get_web_search_tool()
        self.strategy_prompt = ChatPromptTemplate.from_messages([
            ("system", (
                "You are an expert Subscription Cost Optimization AI Agent.\n"
                "Review the ranked optimization recommendations in Indian Rupees (₹), total potential savings, "
                "and real-time live market search findings.\n"
                "Produce a concise, motivating strategic summary (2-3 sentences) advising the user "
                "on how to execute these savings immediately, citing live market pricing or discount options in ₹."
            )),
            ("human", (
                "Total Monthly Potential Savings: ₹{monthly_savings:.2f}\n"
                "Total Annual Potential Savings: ₹{annual_savings:.2f}\n"
                "Number of Recommendations: {rec_count}\n"
                "Top Recommendations:\n{rec_summary}\n\n"
                "Live Web Search Intelligence:\n{live_web_context}\n\n"
                "Provide the strategic summary in ₹ (INR):"
            ))
        ])

    async def optimize_portfolio(
        self,
        subscriptions: List[SubscriptionDTO],
        # pyrefly: ignore [unknown-name]
        spending_profiles: Optional[List[Any]] = None,
        user_id: Optional[str] = "default-user"
    ) -> RankedOptimizations:
        from app.schemas.analyser import AnalyserReport
        fake_report = AnalyserReport(
            user_id=user_id or "default-user",
            total_monthly_spend=sum(s.monthly_cost for s in subscriptions),
            total_annual_spend=sum(s.annual_cost for s in subscriptions),
            currency="INR",
            total_subscriptions_count=len(subscriptions),
            active_subscriptions_count=len([s for s in subscriptions if s.status.value == "ACTIVE"]),
            underutilized_subscriptions_count=0,
            overpriced_subscriptions_count=0,
            spend_by_category={},
            insights_by_subscription=spending_profiles or [],
            portfolio_health_rating="HEALTHY",
            executive_summary=""
        )
        return await self.optimize(analyser_report=fake_report, subscriptions=subscriptions, user_id=user_id)

    async def optimize(
        self,
        analyser_report: AnalyserReport,
        subscriptions: Optional[List[SubscriptionDTO]] = None,
        user_id: Optional[str] = "default-user"
    ) -> RankedOptimizations:
        """
        Generates ranked recommendations based on analyser insights and market plans.
        """
        recommendations: List[OptimizationRecommendation] = []
        active_names = [p.subscription_name for p in analyser_report.insights_by_subscription]

        # 1. Evaluate individual subscriptions from Analyser profiles
        for profile in analyser_report.insights_by_subscription:
            sub_name = profile.subscription_name
            monthly_cost = profile.monthly_cost
            sub_id = profile.subscription_id

            # Rule A: Severely underutilized (dormant / <= 2 active days) -> Suggest Cancellation or Pause
            if profile.is_underutilized and profile.usage_metrics.score < 25.0:
                recommendations.append(OptimizationRecommendation(
                    id=f"rec-cancel-{uuid.uuid4().hex[:6]}",
                    subscription_name=sub_name,
                    subscription_id=sub_id,
                    action_type=OptimizationActionType.CANCEL,
                    current_cost_monthly=monthly_cost,
                    new_estimated_cost_monthly=0.0,
                    monthly_savings=monthly_cost,
                    annual_savings=round(monthly_cost * 12.0, 2),
                    confidence_score=0.95,
                    priority_rank=1,  # Temporary, will re-sort
                    title=f"Cancel Unused {sub_name}",
                    rationale=(
                        f"You were active only {profile.usage_metrics.score:.0f}/100 in usage this month. "
                        f"Cancelling {sub_name} immediately saves ₹{monthly_cost:.2f}/month (₹{monthly_cost * 12:.2f}/year)."
                    ),
                    suggested_target_plan="Cancelled",
                    action_payload={
                        "action": "CANCEL_SUBSCRIPTION",
                        "subscription_id": sub_id,
                        "subscription_name": sub_name
                    }
                ))
            elif profile.is_underutilized:
                # Moderate underutilization -> Suggest pause or cheaper tier
                alternatives = get_market_alternatives(sub_name, monthly_cost)
                if alternatives:
                    alt = alternatives[0]
                    recommendations.append(OptimizationRecommendation(
                        id=f"rec-tier-{uuid.uuid4().hex[:6]}",
                        subscription_name=sub_name,
                        subscription_id=sub_id,
                        action_type=OptimizationActionType.DOWNGRADE_TIER,
                        current_cost_monthly=monthly_cost,
                        new_estimated_cost_monthly=alt["new_monthly_price"],
                        monthly_savings=alt["monthly_savings"],
                        annual_savings=alt["annual_savings"],
                        confidence_score=0.88,
                        priority_rank=2,
                        title=f"Downgrade {sub_name} to {alt['tier']}",
                        rationale=(
                            f"Your current usage ({profile.usage_metrics.score:.0f}/100) doesn't justify the top tier. "
                            f"Switching to {alt['tier']} saves ₹{alt['monthly_savings']:.2f}/mo."
                        ),
                        suggested_target_plan=alt["tier"],
                        action_payload={
                            "action": "DOWNGRADE_SUBSCRIPTION",
                            "subscription_id": sub_id,
                            "target_plan": alt["tier"],
                            "new_price": alt["new_monthly_price"]
                        }
                    ))
                else:
                    recommendations.append(OptimizationRecommendation(
                        id=f"rec-pause-{uuid.uuid4().hex[:6]}",
                        subscription_name=sub_name,
                        subscription_id=sub_id,
                        action_type=OptimizationActionType.PAUSE,
                        current_cost_monthly=monthly_cost,
                        new_estimated_cost_monthly=0.0,
                        monthly_savings=monthly_cost,
                        annual_savings=round(monthly_cost * 12.0, 2),
                        confidence_score=0.80,
                        priority_rank=3,
                        title=f"Pause {sub_name} Membership Temporarily",
                        rationale=(
                            f"Low engagement detected recently. Pausing {sub_name} for 1-3 months saves money "
                            f"without losing account preferences."
                        ),
                        suggested_target_plan="Paused",
                        action_payload={
                            "action": "PAUSE_SUBSCRIPTION",
                            "subscription_id": sub_id,
                            "subscription_name": sub_name
                        }
                    ))

            # Rule B: Overpriced compared to market or has annual discounts
            if not profile.is_underutilized:
                alternatives = get_market_alternatives(sub_name, monthly_cost)
                # pyrefly: ignore [unknown-name]
                bc_str = str(getattr(sub, "billingCycle", "")).upper()
                # pyrefly: ignore [unknown-name]
                desc_str = str(getattr(sub, "description", "")).upper()
                is_already_annual = (
                    "YEARLY" in bc_str or
                    "ANNUALLY" in bc_str or
                    "ANNUAL" in desc_str or
                    monthly_cost <= 585.0
                )
                for alt in alternatives:
                    if alt["type"] == "SWITCH_ANNUAL" and not is_already_annual:
                        recommendations.append(OptimizationRecommendation(
                            id=f"rec-annual-{uuid.uuid4().hex[:6]}",
                            subscription_name=sub_name,
                            subscription_id=sub_id,
                            action_type=OptimizationActionType.SWITCH_ANNUAL,
                            current_cost_monthly=monthly_cost,
                            new_estimated_cost_monthly=alt["new_monthly_price"],
                            monthly_savings=alt["monthly_savings"],
                            annual_savings=alt["annual_savings"],
                            confidence_score=0.85,
                            priority_rank=4,
                            title=f"Switch {sub_name} to Annual Billing",
                            rationale=(
                                f"Since you frequently use {sub_name}, switching from monthly to annual billing "
                                f"unlocks a discounted rate and saves ₹{alt['annual_savings']:.2f}/year."
                            ),
                            suggested_target_plan=alt["tier"],
                            action_payload={
                                "action": "SWITCH_ANNUAL_PLAN",
                                "subscription_id": sub_id,
                                "subscription_name": sub_name,
                                "annual_price": alt.get("annual_price")
                            }
                        ))

        # 2. Check for Bundling Deals across all user services
        bundles = find_applicable_bundles(active_names)
        for b in bundles:
            recommendations.append(OptimizationRecommendation(
                id=f"rec-bundle-{uuid.uuid4().hex[:6]}",
                subscription_name=", ".join(b["matched_services"]).title(),
                subscription_id=None,
                action_type=OptimizationActionType.BUNDLE_DEAL,
                current_cost_monthly=round(b["bundle_monthly_price"] + b["potential_monthly_savings"], 2),
                new_estimated_cost_monthly=b["bundle_monthly_price"],
                monthly_savings=b["potential_monthly_savings"],
                annual_savings=b["potential_annual_savings"],
                confidence_score=0.90,
                priority_rank=2,
                title=f"Combine into {b['bundle_name']}",
                rationale=b["description"],
                suggested_target_plan=b["bundle_name"],
                action_payload={
                    "action": "EXPLORE_BUNDLE",
                    "bundle_name": b["bundle_name"],
                    "target_price": b["bundle_monthly_price"]
                }
            ))

        # 3. Sort recommendations by monthly savings (descending) and assign priority ranks
        recommendations.sort(key=lambda r: r.monthly_savings, reverse=True)
        for idx, rec in enumerate(recommendations, start=1):
            rec.priority_rank = idx

        total_monthly_savings = round(sum(r.monthly_savings for r in recommendations), 2)
        total_annual_savings = round(sum(r.annual_savings for r in recommendations), 2)

        # 4. Fetch Live Web Search Deals & Intelligence (Real-time, without caching)
        live_web_summary = ""
        try:
            live_web_summary = await self.web_search.get_live_deals_summary(active_names)
        except Exception as e:
            logger.warning("Live web search summary gathering failed: %s", e)

        # 5. Generate Strategic Summary via LLM
        rec_summary_lines = [f"- {r.title} (Saves ₹{r.monthly_savings}/mo, Rationale: {r.rationale})" for r in recommendations[:4]]
        rec_summary_str = "\n".join(rec_summary_lines) or "No active recommendations needed."

        try:
            prompt_val = self.strategy_prompt.format_messages(
                monthly_savings=total_monthly_savings,
                annual_savings=total_annual_savings,
                rec_count=len(recommendations),
                rec_summary=rec_summary_str,
                live_web_context=live_web_summary or "No live web deals detected."
            )
            llm_res = await self.llm.ainvoke(prompt_val)
            strategic_summary = llm_res.content if hasattr(llm_res, "content") else str(llm_res)
        except Exception as e:
            logger.warning("LLM generation failed for Optimizer strategic summary: %s", e)
            strategic_summary = (
                f"You can save up to ₹{total_monthly_savings:.2f}/month (₹{total_annual_savings:.2f}/year) "
                f"by acting on {len(recommendations)} optimization opportunities. "
                f"Cancelling inactive subscriptions and switching frequent apps to annual billing yield the highest ROI."
            )

        # 6. Generate Action Cards for UI One-Click Execution
        action_cards: List[ActionCard] = []
        portal_map = {
            "netflix": "https://www.netflix.com/youraccount",
            "spotify": "https://www.spotify.com/account/overview/",
            "disney+ hotstar": "https://www.hotstar.com/in/my-account",
            "hotstar": "https://www.hotstar.com/in/my-account",
            "amazon prime": "https://www.amazon.in/mc/manageyourprime",
            "apple one": "https://support.apple.com/billing",
            "github": "https://github.com/settings/billing",
            "aws": "https://console.aws.amazon.com/billing/home"
        }

        for rec in recommendations[:6]:
            act_type = ActionType.DOWNGRADE_SUBSCRIPTION
            if rec.action_type == OptimizationActionType.CANCEL:
                act_type = ActionType.CANCEL_SUBSCRIPTION
            elif rec.action_type == OptimizationActionType.SWITCH_ANNUAL:
                act_type = ActionType.SWITCH_ANNUAL_PLAN
            elif rec.action_type == OptimizationActionType.BUNDLE_DEAL:
                act_type = ActionType.EXPLORE_BUNDLE
            elif rec.action_type == OptimizationActionType.PAUSE:
                act_type = ActionType.PAUSE_SUBSCRIPTION

            first_name = rec.subscription_name.split(",")[0].strip().lower()
            portal_url = portal_map.get(first_name)

            action_cards.append(ActionCard(
                action_id=f"act-{uuid.uuid4().hex[:8]}",
                title=rec.title,
                description=rec.rationale,
                action_type=act_type,
                target_subscription_id=rec.subscription_id,
                target_subscription_name=rec.subscription_name,
                payload=rec.action_payload,
                requires_confirmation=True,
                confirmation_title=f"Confirm: {rec.title}",
                confirmation_message=f"Are you sure you want to apply this optimization? {rec.rationale}",
                provider_portal_url=portal_url,
                estimated_monthly_savings=rec.monthly_savings,
                button_text="Apply Action"
            ))

        return RankedOptimizations(
            user_id=user_id,
            total_potential_monthly_savings=total_monthly_savings,
            total_potential_annual_savings=total_annual_savings,
            currency="INR",
            recommendations_count=len(recommendations),
            recommendations=recommendations,
            action_cards=action_cards,
            strategic_summary=strategic_summary.strip()
        )
