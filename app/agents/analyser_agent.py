import logging
from typing import List, Optional, Dict, Any
# pyrefly: ignore [missing-import]
from langchain_core.prompts import ChatPromptTemplate
from app.agents.llm.client import get_chat_llm
from app.agents.tools.benchmark_data import get_category_benchmark
from app.schemas.subscription import SubscriptionDTO, UsageSignal, BillingHistoryItem
from app.schemas.analyser import (
    UsageScore,
    CategoryBenchmark,
    SubscriptionInsightProfile,
    AnalyserReport
)

logger = logging.getLogger(__name__)


class SubscriptionAnalyserAgent:
    """
    Subscription Analyser Agent:
    Analyses usage frequency, spend metrics, and category benchmarks to build
    a per-user insight profile and identify underutilized or overpriced subscriptions.
    """

    def __init__(self):
        self.llm = get_chat_llm(temperature=0.2)
        self.summary_prompt = ChatPromptTemplate.from_messages([
            ("system", (
                "You are an expert Subscription & Personal Finance Analyser AI Agent.\n"
                "Analyze the provided user subscription portfolio in Indian Rupees (₹), usage metrics, and category benchmarks.\n"
                "Provide an analytical, concise executive summary (2-3 sentences) highlighting total monthly spend in ₹, "
                "the most underutilized or wasteful subscriptions, and overall financial health."
            )),
            ("human", (
                "Portfolio Data:\n"
                "Total Monthly Spend: ₹{total_monthly_spend:.2f}\n"
                "Active Subscriptions: {active_count}\n"
                "Underutilized Subscriptions: {underutilized_count}\n"
                "Category Breakdown: {category_breakdown}\n"
                "Subscriptions Details:\n{subs_summary}\n\n"
                "Provide the executive summary in ₹ (INR):"
            ))
        ])

    def calculate_usage_score(self, sub: SubscriptionDTO, signal: Optional[UsageSignal]) -> UsageScore:
        """
        Calculates normalized usage score (0-100), cost per active day, and cost per hour.
        """
        if not signal:
            # Default moderate score if telemetry is missing
            return UsageScore(
                score=50.0,
                tier="MODERATE",
                cost_per_active_day=round(sub.monthly_cost / 15.0, 2),
                cost_per_hour=round(sub.monthly_cost / 10.0, 2),
                efficiency_rating="GOOD"
            )

        # Weighted usage calculation
        days_factor = min(signal.active_days_last_30 / 20.0, 1.0) * 40.0   # up to 40 pts
        freq_factor = (1.0 if signal.login_frequency in ["DAILY", "MULTIPLE_DAILY"] else 0.6) * 30.0
        hrs_factor = min(signal.hours_streamed_or_used_last_30 / 15.0, 1.0) * 30.0
        raw_score = days_factor + freq_factor + hrs_factor

        tier = "VERY_HIGH" if raw_score >= 80 else ("HIGH" if raw_score >= 60 else ("MODERATE" if raw_score >= 40 else "LOW"))
        rating = "EXCELLENT" if raw_score >= 70 else ("GOOD" if raw_score >= 45 else "POOR_VALUE")

        active_days = max(signal.active_days_last_30, 1)
        total_hours = max(signal.hours_streamed_or_used_last_30, 0.5)

        return UsageScore(
            score=round(raw_score, 1),
            tier=tier,
            cost_per_active_day=round(sub.monthly_cost / active_days, 2),
            cost_per_hour=round(sub.monthly_cost / total_hours, 2),
            efficiency_rating=rating
        )

    def calculate_category_benchmark(self, sub: SubscriptionDTO) -> CategoryBenchmark:
        """
        Compares subscription spend against industry benchmark for its category.
        """
        benchmark = get_category_benchmark(sub.category, user_amount=sub.monthly_cost)
        avg_market = benchmark.get("avg_monthly_spend", max(15.0, sub.monthly_cost))
        user_monthly = sub.monthly_cost

        delta = round(((user_monthly - avg_market) / avg_market) * 100.0, 1) if avg_market > 0 else 0.0

        if delta > 40.0:
            status = "SIGNIFICANTLY_EXPENSIVE"
        elif delta > 10.0:
            status = "ABOVE_AVERAGE"
        elif delta < -10.0:
            status = "BELOW_AVERAGE"
        else:
            status = "AVERAGE"

        return CategoryBenchmark(
            category=sub.category,
            average_market_monthly_spend=avg_market,
            user_monthly_spend=user_monthly,
            delta_percentage=delta,
            benchmark_status=status
        )


    async def analyse(
        self,
        subscriptions: List[SubscriptionDTO],
        usage_signals: Optional[List[UsageSignal]] = None,
        # pyrefly: ignore [unknown-name]
        billing_history: Optional[List[Any]] = None,
        user_id: Optional[str] = "default-user"
    ) -> AnalyserReport:
        return await self.analyse_subscriptions(
            subscriptions=subscriptions,
            usage_signals=usage_signals,
            user_id=user_id or "default-user"
        )

    async def analyse_subscriptions(
        self,
        subscriptions: List[SubscriptionDTO],
        usage_signals: Optional[List[UsageSignal]] = None,
        user_id: str = "default-user"
    ) -> AnalyserReport:
        """
        Runs comprehensive heuristic and LLM analysis over a list of active subscriptions.
        """
        usage_map = {s.subscription_id: s for s in (usage_signals or []) if s.subscription_id}
        spend_by_category: Dict[str, float] = {}
        profiles: List[SubscriptionInsightProfile] = []
        total_monthly_spend = 0.0
        active_count = 0
        underutilized_count = 0
        overpriced_count = 0

        for sub in subscriptions:
            if sub.status.value != "ACTIVE":
                continue

            active_count += 1
            monthly = sub.monthly_cost
            total_monthly_spend += monthly
            spend_by_category[sub.category] = round(spend_by_category.get(sub.category, 0.0) + monthly, 2)

            signal = usage_map.get(str(sub.id))
            usage_metric = self.calculate_usage_score(sub, signal)

            benchmark_metric = self.calculate_category_benchmark(sub)

            is_underutilized = usage_metric.score < 40.0
            is_overpriced = benchmark_metric.delta_percentage > 25.0

            if is_underutilized:
                underutilized_count += 1
            if is_overpriced:
                overpriced_count += 1

            findings = []
            flags = []

            if is_underutilized:
                findings.append(f"Low usage detected: Active only {signal.active_days_last_30 if signal else 0} days in past 30 days.")
                flags.append("UNDERUTILIZED_RISK")
            else:
                findings.append(f"Healthy engagement: Active {signal.active_days_last_30 if signal else 15} days in past 30 days.")

            if is_overpriced:
                findings.append(f"Cost is {benchmark_metric.delta_percentage}% above market benchmark (₹{benchmark_metric.average_market_monthly_spend:.2f}/mo).")
                flags.append("OVERPRICED_PLAN")

            if usage_metric.cost_per_active_day > 100.0:
                flags.append("HIGH_COST_PER_USE")
                findings.append(f"High cost-per-use: ₹{usage_metric.cost_per_active_day:.2f} per active day.")

            insight_summary = (
                f"{sub.name} ({sub.category}): ₹{monthly:.2f}/mo. "
                f"Usage score is {usage_metric.score}/100 ({usage_metric.tier}). "
                f"Value rating: {usage_metric.efficiency_rating}."
            )

            profiles.append(SubscriptionInsightProfile(
                subscription_id=str(sub.id) if sub.id else None,
                subscription_name=sub.name,
                category=sub.category,
                monthly_cost=monthly,
                annual_cost=sub.annual_cost,
                currency="INR",
                billing_cycle=sub.billingCycle.value,
                usage_metrics=usage_metric,
                category_benchmark=benchmark_metric,
                is_underutilized=is_underutilized,
                is_overpriced=is_overpriced,
                insight_summary=insight_summary,
                key_findings=findings,
                risk_flags=flags
            ))

        total_annual_spend = round(total_monthly_spend * 12.0, 2)
        total_monthly_spend = round(total_monthly_spend, 2)

        # Portfolio health rating
        if underutilized_count >= 2 or overpriced_count >= 2:
            health = "NEEDS_ATTENTION"
        elif underutilized_count > 0:
            health = "HEALTHY"
        else:
            health = "EXCELLENT"

        # Generate Executive Summary using LLM with algorithmic fallback
        subs_text_list = [f"- {p.subscription_name} (₹{p.monthly_cost}/mo, Usage: {p.usage_metrics.score}/100, Underutilized: {p.is_underutilized})" for p in profiles]
        subs_summary_str = "\n".join(subs_text_list)

        try:
            prompt_val = self.summary_prompt.format_messages(
                total_monthly_spend=total_monthly_spend,
                active_count=active_count,
                underutilized_count=underutilized_count,
                category_breakdown=str(spend_by_category),
                subs_summary=subs_summary_str
            )
            llm_res = await self.llm.ainvoke(prompt_val)
            exec_summary = llm_res.content if hasattr(llm_res, "content") else str(llm_res)
        except Exception as e:
            logger.warning("LLM generation failed for Analyser executive summary, using fallback: %s", e)
            exec_summary = (
                f"You currently spend ₹{total_monthly_spend:.2f} across {active_count} active subscriptions. "
                f"{underutilized_count} subscriptions are currently underutilized. "
                f"Your highest spending category is {max(spend_by_category, key=spend_by_category.get) if spend_by_category else 'N/A'}."
            )

        return AnalyserReport(
            user_id=user_id,
            total_monthly_spend=total_monthly_spend,
            total_annual_spend=total_annual_spend,
            currency="INR",
            total_subscriptions_count=len(subscriptions),
            active_subscriptions_count=active_count,
            underutilized_subscriptions_count=underutilized_count,
            overpriced_subscriptions_count=overpriced_count,
            spend_by_category=spend_by_category,
            insights_by_subscription=profiles,
            overall_portfolio_health=health,
            executive_summary=exec_summary.strip()
        )
