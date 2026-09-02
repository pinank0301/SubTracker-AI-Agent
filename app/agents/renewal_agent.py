import logging
from typing import List, Optional, Dict
from datetime import date, datetime, timedelta
# pyrefly: ignore [missing-import]
from langchain_core.prompts import ChatPromptTemplate
from app.agents.llm.client import get_chat_llm
from app.schemas.subscription import SubscriptionDTO, BillingHistoryItem, UsageSignal, BillingCycle
from app.schemas.renewal import (
    RenewalRiskLevel,
    PriceHikePrediction,
    SubscriptionRenewalRisk,
    RenewalRiskAssessment
)

logger = logging.getLogger(__name__)


class RenewalPredictionAgent:
    """
    Renewal Prediction Agent:
    Predicts upcoming renewal dates, assesses silent auto-renewal risks, detects price hikes,
    and calculates user churn/cancel likelihood dynamically based on actual usage patterns.
    """

    def __init__(self):
        self.llm = get_chat_llm(temperature=0.2)
        self.summary_prompt = ChatPromptTemplate.from_messages([
            ("system", (
                "You are an expert Proactive Renewal & Churn Risk Prediction AI Agent.\n"
                "Review the upcoming renewal risks, silent renewals, and potential price hikes.\n"
                "Provide an urgent, highly actionable executive summary (2-3 sentences) alerting the user "
                "to upcoming renewals they should cancel or review immediately."
            )),
            ("human", (
                "30-Day Upcoming Spend: ${upcoming_spend:.2f}\n"
                "High/Critical Risk Subscriptions Count: {high_risk_count}\n"
                "Urgent Renewals (< 7 days): {urgent_count}\n"
                "Risk Breakdown:\n{risks_summary}\n\n"
                "Provide the executive summary:"
            ))
        ])

    def assess_single_subscription(
        self,
        sub: SubscriptionDTO,
        signal: Optional[UsageSignal],
        history: Optional[List[BillingHistoryItem]]
    ) -> SubscriptionRenewalRisk:
        """
        Calculates renewal risk score, churn likelihood, and detects price hikes dynamically.
        """
        today = date.today()
        renewal_dt = today + timedelta(days=14)  # Default estimation if date not present
        if sub.renewalDate:
            try:
                renewal_dt = datetime.strptime(sub.renewalDate[:10], "%Y-%m-%d").date()
            except Exception:
                pass

        days_until = (renewal_dt - today).days

        # Predict next amount and detect dynamic price changes from billing history
        predicted_amount = sub.amount
        price_hike_info = None

        if history:
            matching_tx = [h for h in history if h.subscription_name.lower() == sub.name.lower() or h.subscription_id == sub.id]
            if matching_tx:
                recent_tx = matching_tx[0]
                if recent_tx.price_change_from_previous and recent_tx.price_change_from_previous > 0:
                    price_hike_info = PriceHikePrediction(
                        subscription_name=sub.name,
                        is_price_hike_likely=True,
                        estimated_hike_percentage=recent_tx.price_change_from_previous,
                        estimated_new_amount=round(sub.amount * (1.0 + recent_tx.price_change_from_previous / 100.0), 2),
                        confidence=0.85,
                        market_signals=["Recent billing transaction reflects an active price adjustment."]
                    )

        # Calculate Churn / Cancellation Likelihood dynamically
        churn_score = 15.0  # Base neutral likelihood
        risk_factors = []

        if signal:
            if signal.active_days_last_30 <= 2:
                churn_score += 45.0
                risk_factors.append(f"Near-zero usage ({signal.active_days_last_30} active days in past month)")
            elif signal.active_days_last_30 <= 6:
                churn_score += 25.0
                risk_factors.append("Low monthly usage")

            if signal.engagement_trend == "DORMANT":
                churn_score += 20.0
                risk_factors.append("Dormant engagement trend")
            elif signal.engagement_trend == "DECLINING":
                churn_score += 15.0
                risk_factors.append("Declining usage trend")

        if price_hike_info and price_hike_info.is_price_hike_likely:
            churn_score += 15.0
            risk_factors.append(f"Upcoming {price_hike_info.estimated_hike_percentage}% price increase")

        churn_score = max(0.0, min(100.0, round(churn_score, 1)))

        # Silent Auto-Renewal Risk
        is_silent = False
        if days_until <= 7 and churn_score >= 40.0:
            is_silent = True
            risk_factors.append(f"Auto-renewal in {days_until} days for underutilized service")
        elif sub.billingCycle in [BillingCycle.ANNUALLY, BillingCycle.QUARTERLY] and days_until <= 14:
            is_silent = True
            risk_factors.append(f"Upcoming high-cost {sub.billingCycle.value} auto-charge")

        # Total Renewal Risk Score (0-100)
        urgency_factor = max(0.0, (30.0 - min(days_until, 30.0)) / 30.0) * 30.0
        renewal_risk_score = round((churn_score * 0.7) + urgency_factor, 1)
        renewal_risk_score = max(0.0, min(100.0, renewal_risk_score))

        # Risk Level
        if renewal_risk_score >= 70.0:
            level = RenewalRiskLevel.CRITICAL
            suggestion = f"Action Needed: Cancel or pause {sub.name} before {renewal_dt.isoformat()} to avoid a ₹{predicted_amount:.2f} charge."
        elif renewal_risk_score >= 45.0:
            level = RenewalRiskLevel.HIGH
            suggestion = f"Review plan: Set a reminder for {renewal_dt.isoformat()} or consider downgrading."
        elif renewal_risk_score >= 25.0:
            level = RenewalRiskLevel.MEDIUM
            suggestion = f"Monitor usage before renewal on {renewal_dt.isoformat()}."
        else:
            level = RenewalRiskLevel.LOW
            suggestion = f"Healthy subscription. Next standard renewal on {renewal_dt.isoformat()}."

        return SubscriptionRenewalRisk(
            subscription_id=str(sub.id) if sub.id else None,
            subscription_name=sub.name,
            category=sub.category,
            current_amount=sub.amount,
            billing_cycle=sub.billingCycle.value,
            predicted_renewal_date=renewal_dt.isoformat(),
            predicted_renewal_amount=predicted_amount,
            days_until_renewal=max(0, days_until),
            is_silent_auto_renewal=is_silent,
            churn_likelihood_score=churn_score,
            renewal_risk_score=renewal_risk_score,
            risk_level=level,
            price_hike=price_hike_info,
            risk_factors=risk_factors,
            proactive_suggestion=suggestion
        )

    async def predict_renewals(
        self,
        subscriptions: List[SubscriptionDTO],
        billing_history: Optional[List[BillingHistoryItem]] = None,
        usage_signals: Optional[List[UsageSignal]] = None,
        user_id: Optional[str] = "default-user"
    ) -> RenewalRiskAssessment:
        """
        Runs comprehensive renewal predictions across all active subscriptions.
        """
        signals_map: Dict[str, UsageSignal] = {}
        if usage_signals:
            for s in usage_signals:
                key = (s.subscription_id or s.subscription_name).lower()
                signals_map[key] = s
                signals_map[s.subscription_name.lower()] = s

        assessments: List[SubscriptionRenewalRisk] = []
        total_upcoming_30d_spend = 0.0
        unwanted_spend = 0.0
        urgent_count = 0
        high_risk_count = 0

        for sub in subscriptions:
            if sub.status.value != "ACTIVE":
                continue

            signal = signals_map.get(str(sub.id).lower()) or signals_map.get(sub.name.lower())
            assessment = self.assess_single_subscription(sub, signal, billing_history)
            assessments.append(assessment)

            if assessment.days_until_renewal <= 30:
                total_upcoming_30d_spend += assessment.predicted_renewal_amount

            if assessment.days_until_renewal <= 7:
                urgent_count += 1

            if assessment.risk_level in [RenewalRiskLevel.CRITICAL, RenewalRiskLevel.HIGH]:
                high_risk_count += 1
                unwanted_spend += assessment.predicted_renewal_amount

        # Sort by urgency and risk score
        assessments.sort(key=lambda a: (a.days_until_renewal, -a.renewal_risk_score))

        # Generate summary via LLM
        risks_lines = [
            f"- {a.subscription_name}: Renews in {a.days_until_renewal} days (₹{a.predicted_renewal_amount:.2f}). "
            f"Risk: {a.risk_level.value} (Score: {a.renewal_risk_score}). Factors: {', '.join(a.risk_factors)}"
            for a in assessments
        ]
        risks_summary_str = "\n".join(risks_lines) or "No active subscriptions renewing soon."

        try:
            prompt_val = self.summary_prompt.format_messages(
                upcoming_spend=total_upcoming_30d_spend,
                high_risk_count=high_risk_count,
                urgent_count=urgent_count,
                risks_summary=risks_summary_str
            )
            llm_res = await self.llm.ainvoke(prompt_val)
            exec_summary = llm_res.content if hasattr(llm_res, "content") else str(llm_res)
        except Exception as e:
            logger.warning("LLM generation failed for Renewal summary: %s", e)
            exec_summary = (
                f"You have ₹{total_upcoming_30d_spend:.2f} scheduled in renewals over the next 30 days. "
                f"{urgent_count} subscriptions renew within 7 days. "
                f"We flagged {high_risk_count} subscriptions with high renewal risk where proactive action can prevent unwanted charges."
            )

        return RenewalRiskAssessment(
            user_id=user_id,
            total_upcoming_30d_renewal_spend=round(total_upcoming_30d_spend, 2),
            urgent_renewals_count=urgent_count,
            high_risk_renewals_count=high_risk_count,
            potential_unwanted_renewal_spend=round(unwanted_spend, 2),
            subscription_assessments=assessments,
            urgent_action_required=(urgent_count > 0 and high_risk_count > 0),
            executive_summary=exec_summary.strip()
        )
