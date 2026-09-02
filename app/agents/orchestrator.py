import logging
import uuid
from typing import List, Optional, Dict, Any
# pyrefly: ignore [missing-import]
from langchain_core.prompts import ChatPromptTemplate
# pyrefly: ignore [missing-import]
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

from app.agents.llm.client import get_chat_llm
from app.agents.guardrails.security_guardrail import SecurityGuardrail
from app.agents.guardrails.domain_guardrail import DomainGuardrail
from app.agents.memory.session_memory import get_session_memory
from app.agents.tools.subscription_client import get_subscription_client
from app.agents.analyser_agent import SubscriptionAnalyserAgent
from app.agents.optimizer_agent import SubscriptionOptimizerAgent
from app.agents.renewal_agent import RenewalPredictionAgent
from app.agents.tools.market_plans import get_provider_portal_url

from app.schemas.subscription import SubscriptionDTO, UsageSignal
from app.schemas.analyser import AnalyserReport
from app.schemas.optimizer import RankedOptimizations
from app.schemas.renewal import RenewalRiskAssessment
from app.schemas.chat import (
    ChatRequest,
    ChatResponse,
    ActionCard,
    ActionType,
    GuardrailStatus,
    WebSearchSource
)
from app.agents.tools.web_search_tool import SubscriptionWebSearchTool

logger = logging.getLogger(__name__)

VERIFIED_PROVIDER_SOURCES = {
    "netflix": {
        "title": "Netflix Help Center - Plans & Pricing",
        "url": "https://help.netflix.com/en/node/24926",
        "domain": "help.netflix.com",
        "snippet": "Official Netflix India plans: Mobile (₹149/mo), Basic (₹199/mo), Standard (₹499/mo), Premium (₹649/mo)."
    },
    "spotify": {
        "title": "Spotify Premium India - Plans & Pricing",
        "url": "https://www.spotify.com/in-en/premium/",
        "domain": "spotify.com",
        "snippet": "Spotify Individual (₹119/mo), Duo (₹149/mo), Family (₹179/mo), Student (₹59/mo)."
    },
    "hotstar": {
        "title": "Disney+ Hotstar Subscription Plans",
        "url": "https://www.hotstar.com/in/subscribe",
        "domain": "hotstar.com",
        "snippet": "Disney+ Hotstar Super (₹899/yr) and Premium (₹1499/yr or ₹299/mo)."
    },
    "disney": {
        "title": "Disney+ Hotstar Subscription Plans",
        "url": "https://www.hotstar.com/in/subscribe",
        "domain": "hotstar.com",
        "snippet": "Disney+ Hotstar Super (₹899/yr) and Premium (₹1499/yr or ₹299/mo)."
    },
    "apple": {
        "title": "Apple One India - All-in-one Subscription Bundle",
        "url": "https://www.apple.com/in/apple-one/",
        "domain": "apple.com",
        "snippet": "Apple One combines Apple Music, Apple TV+, Apple Arcade, and iCloud+ (₹195/mo individual)."
    },
    "amazon": {
        "title": "Amazon Prime India Membership & Benefits",
        "url": "https://www.amazon.in/prime",
        "domain": "amazon.in",
        "snippet": "Amazon Prime India (₹299/mo, ₹1499/yr) with Prime Video, Music, and free fast shipping."
    },
    "prime": {
        "title": "Amazon Prime India Membership & Benefits",
        "url": "https://www.amazon.in/prime",
        "domain": "amazon.in",
        "snippet": "Amazon Prime India (₹299/mo, ₹1499/yr) with Prime Video, Music, and free fast shipping."
    },
    "youtube": {
        "title": "YouTube Premium India Plans",
        "url": "https://www.youtube.com/premium",
        "domain": "youtube.com",
        "snippet": "YouTube Premium (₹129/mo individual, ₹189/mo family, ₹79/mo student) with ad-free playback and Music."
    },
    "chatgpt": {
        "title": "OpenAI ChatGPT Plus & Team Pricing",
        "url": "https://openai.com/chatgpt/pricing/",
        "domain": "openai.com",
        "snippet": "ChatGPT Plus ($20/mo / ~₹1,650) with access to GPT-4o and advanced data analysis."
    },
    "github": {
        "title": "GitHub Copilot & Pro Subscription Pricing",
        "url": "https://github.com/pricing",
        "domain": "github.com",
        "snippet": "GitHub Copilot Individual ($10/mo / ~₹830) and GitHub Pro ($4/mo)."
    }
}


class ConversationalOrchestratorAgent:
    """
    Conversational AI Agent & Master Orchestrator:
    - Enforces LangChain Security & Domain Guardrails.
    - Manages Persistent PostgreSQL Conversation Memory with Cross-Session Context.
    - Dynamically orchestrates specialized worker agents:
        * Subscription Analyser Agent
        * Subscription Optimizer Agent
        * Renewal Prediction Agent
    - Synthesizes findings into natural-language conversational responses.
    - Generates actionable UI cards for one-click subscription operations.
    """

    def __init__(self):
        self.security_guardrail = SecurityGuardrail()
        self.domain_guardrail = DomainGuardrail()
        self.memory = get_session_memory()
        self.sub_client = get_subscription_client()
        self.web_search_tool = SubscriptionWebSearchTool()

        # Worker Agents
        self.analyser_agent = SubscriptionAnalyserAgent()
        self.optimizer_agent = SubscriptionOptimizerAgent()
        self.renewal_agent = RenewalPredictionAgent()

        self.llm = get_chat_llm(temperature=0.3)

        self.conversational_prompt = ChatPromptTemplate.from_messages([
            ("system", (
                "You are SubTracker AI, an elite autonomous Financial Advisor and Subscription Intelligence Copilot.\n"
                "You provide sharp, concise, actionable, and beautifully formatted financial analysis on recurring subscriptions.\n\n"
                "Formatting Guidelines:\n"
                "- Always state currency in Indian Rupees (₹) unless specified otherwise.\n"
                "- Use clean, structured GitHub Markdown with headings (###), bold key metrics, bullet lists, and comparison tables where helpful.\n"
                "- When bolding amounts, ALWAYS place the currency symbol inside the bold tags, e.g. **₹699.00** (NEVER write **₹**699).\n"
                "- When referencing official provider plans, portals, or search results, cite them with clickable Markdown links e.g. [Netflix Plans](https://help.netflix.com/en/node/24926).\n"
                "- When analyzing spend or suggesting savings, clearly list the subscription name, monthly cost, and exact annual savings.\n"
                "- Be direct, polite, highly analytical, and avoid repetitive boilerplate disclaimers.\n"
                "- If the user asks about deals, renewals, or optimizations, provide prioritized recommendations with estimated savings in ₹."
            )),
            ("human", (
                "User Query: {query}\n\n"
                "Active Subscriptions Portfolio:\n{subs_context}\n\n"
                "Specialized Multi-Agent Insights:\n{agent_insights}\n\n"
                "Verified Web Search & Market Sources:\n{sources_context}\n\n"
                "Prior Session Context:\n{cross_session_context}\n\n"
                "Recent Dialogue Turn History:\n{history}\n\n"
                "Respond with an insightful, well-structured markdown analysis including clickable web citations where relevant:"
            ))
        ])

    async def process_chat(self, request: ChatRequest) -> ChatResponse:
        """
        Main entry point for handling user conversational interactions.
        """
        session_id = request.session_id or f"sess-{uuid.uuid4().hex[:8]}"
        user_id = request.user_id or "default-user"
        raw_message = request.message

        # =========================================================================
        # 1. LangChain Security Guardrail (Prompt Injection / Jailbreak Check)
        # =========================================================================
        is_safe, sanitized_query, sec_flags = self.security_guardrail.validate_input(raw_message)
        if not is_safe:
            return ChatResponse(
                response="I'm sorry, but your message contained invalid patterns or security overrides. How can I assist you with your subscriptions today?",
                session_id=session_id,
                intent_detected="SECURITY_BLOCKED",
                agents_invoked=[],
                action_cards=[],
                guardrail_status=GuardrailStatus(
                    passed=False,
                    domain_valid=False,
                    security_valid=False,
                    category="INJECTION_ATTEMPT",
                    rejection_reason="Blocked due to security policy violations."
                )
            )

        # =========================================================================
        # 2. LangChain Domain Boundary Guardrail (Subscription Service Scope)
        # =========================================================================
        is_in_domain, detected_intent, domain_meta = await self.domain_guardrail.validate_domain(sanitized_query)
        if not is_in_domain:
            return ChatResponse(
                response=self.domain_guardrail.OUT_OF_DOMAIN_RESPONSE,
                session_id=session_id,
                intent_detected="OUT_OF_DOMAIN",
                agents_invoked=[],
                action_cards=[],
                guardrail_status=GuardrailStatus(
                    passed=False,
                    domain_valid=False,
                    security_valid=True,
                    category="OUT_OF_DOMAIN",
                    rejection_reason="Query is outside the subscription management domain."
                )
            )

        # =========================================================================
        # 3. Retrieve Subscription & Behavioral Data
        # =========================================================================
        subscriptions = request.subscriptions
        if not subscriptions:
            subscriptions = await self.sub_client.get_user_subscriptions(user_id=user_id)

        # Telemetry is purely derived from user payload or evaluated dynamically
        usage_signals = request.usage_signals or []
        billing_history = None

        # =========================================================================
        # 4. Multi-Agent Orchestration & Delegation
        # =========================================================================
        agents_invoked: List[str] = []
        agent_insights_parts: List[str] = []
        action_cards: List[ActionCard] = []

        analyser_report: Optional[AnalyserReport] = None
        ranked_optimizations: Optional[RankedOptimizations] = None
        renewal_assessment: Optional[RenewalRiskAssessment] = None

        query_lower = sanitized_query.lower()

        # Decide which agents to run based on intent and query semantics
        needs_analysis = detected_intent in ["ANALYSE", "OPTIMIZE", "GENERAL_QA"] or any(
            k in query_lower for k in ["spend", "cost", "how much", "breakdown", "category", "usage", "overview", "all", "subscriptions"]
        )
        needs_optimization = detected_intent in ["OPTIMIZE", "ACTION", "GENERAL_QA"] or any(
            k in query_lower for k in ["save", "saving", "cheaper", "optimize", "switch", "bundle", "discount", "cut", "reduce"]
        )
        needs_renewal = detected_intent in ["RENEWAL", "GENERAL_QA"] or any(
            k in query_lower for k in ["renew", "renewal", "upcoming", "hike", "charge", "auto-renew", "predict"]
        )
        is_direct_action = any(
            k in query_lower for k in ["cancel", "pause", "downgrade", "change plan"]
        )

        # Execute Analyser Agent
        if needs_analysis or needs_optimization:
            agents_invoked.append("Subscription Analyser Agent")
            analyser_report = await self.analyser_agent.analyse(
                subscriptions=subscriptions,
                usage_signals=usage_signals,
                billing_history=billing_history,
                user_id=user_id
            )
            agent_insights_parts.append(
                f"[Analyser Agent]: Total Monthly Spend = ₹{analyser_report.total_monthly_spend:.2f}. "
                f"Active Subscriptions = {analyser_report.active_subscriptions_count}. "
                f"Underutilized = {analyser_report.underutilized_subscriptions_count}. "
                f"Summary: {analyser_report.executive_summary}"
            )

        # Execute Optimizer Agent
        if needs_optimization and analyser_report:
            agents_invoked.append("Subscription Optimizer Agent")
            ranked_optimizations = await self.optimizer_agent.optimize(
                analyser_report=analyser_report,
                subscriptions=subscriptions,
                user_id=user_id
            )
            agent_insights_parts.append(
                f"[Optimizer Agent]: Potential Monthly Savings = ₹{ranked_optimizations.total_potential_monthly_savings:.2f}/mo. "
                f"Found {ranked_optimizations.recommendations_count} recommendations. "
                f"Strategy: {ranked_optimizations.strategic_summary}"
            )

            # Create Action Cards from top recommendations
            for rec in ranked_optimizations.recommendations[:3]:
                sub_name = rec.subscription_name
                portal_url = get_provider_portal_url(sub_name)
                action_type_enum = ActionType(rec.action_payload.get("action", "DOWNGRADE_SUBSCRIPTION"))
                
                if action_type_enum == ActionType.CANCEL_SUBSCRIPTION:
                    conf_title = f"Update Tracker: Cancel {sub_name}"
                    conf_msg = (
                        f"This will mark {sub_name} as cancelled in your budget tracker and stop future reminders. "
                        f"Please ensure you also cancel your membership on {sub_name}'s official portal."
                    )
                elif action_type_enum == ActionType.SWITCH_ANNUAL_PLAN:
                    conf_title = f"Update Tracker: Switch {sub_name} to Annual"
                    conf_msg = (
                        f"This will update your budget to the annual discounted rate (saving ₹{rec.monthly_savings:.2f}/mo). "
                        f"Please ensure you switch your billing cycle to annual on {sub_name}'s account settings."
                    )
                else:
                    conf_title = f"Update Tracker: {rec.title}"
                    conf_msg = (
                        f"This will adjust your tracked subscription plan for {sub_name}. "
                        f"Please verify this plan change directly on {sub_name}'s portal."
                    )

                action_cards.append(ActionCard(
                    action_id=rec.id,
                    title=rec.title,
                    description=rec.rationale,
                    action_type=action_type_enum,
                    target_subscription_id=rec.subscription_id,
                    target_subscription_name=sub_name,
                    payload=rec.action_payload,
                    requires_confirmation=True,
                    confirmation_title=conf_title,
                    confirmation_message=conf_msg,
                    provider_portal_url=portal_url,
                    estimated_monthly_savings=rec.monthly_savings,
                    button_text=f"Save ₹{rec.monthly_savings:.2f}/mo"
                ))

        # Execute Renewal Prediction Agent
        if needs_renewal:
            agents_invoked.append("Renewal Prediction Agent")
            renewal_assessment = await self.renewal_agent.predict_renewals(
                subscriptions=subscriptions,
                billing_history=billing_history,
                usage_signals=usage_signals,
                user_id=user_id
            )
            agent_insights_parts.append(
                f"[Renewal Prediction Agent]: Upcoming 30-day renewals spend = ₹{renewal_assessment.total_upcoming_30d_renewal_spend:.2f}. "
                f"High-risk renewals = {renewal_assessment.high_risk_renewals_count}. "
                f"Summary: {renewal_assessment.executive_summary}"
            )

            # Create Alert Action Cards for high-risk upcoming renewals
            for risk_sub in renewal_assessment.subscription_assessments:
                if risk_sub.days_until_renewal <= 7 and risk_sub.risk_level.value in ["CRITICAL", "HIGH"]:
                    sub_name = risk_sub.subscription_name
                    action_cards.append(ActionCard(
                        action_id=f"alert-cancel-{risk_sub.subscription_id or sub_name}",
                        title=f"Cancel {sub_name} before renewal",
                        description=f"Auto-renews in {risk_sub.days_until_renewal} days for ₹{risk_sub.predicted_renewal_amount:.2f}.",
                        action_type=ActionType.CANCEL_SUBSCRIPTION,
                        target_subscription_id=risk_sub.subscription_id,
                        target_subscription_name=sub_name,
                        payload={"action": "CANCEL_SUBSCRIPTION", "subscription_name": sub_name},
                        requires_confirmation=True,
                        confirmation_title=f"Update Tracker: Cancel {sub_name}",
                        confirmation_message=(
                            f"This will mark {sub_name} as cancelled in your budget tracker before renewal on "
                            f"{risk_sub.renewal_date or 'soon'}. Ensure you cancel on {sub_name}'s website."
                        ),
                        provider_portal_url=get_provider_portal_url(sub_name),
                        estimated_monthly_savings=risk_sub.predicted_renewal_amount,
                        button_text="Cancel Subscription"
                    ))

        # Handle specific direct action keywords (e.g. "cancel gym", "cancel netflix")
        if is_direct_action:
            direct_cards = []
            for sub in subscriptions:
                name_lower = sub.name.lower()
                tokens = [t.strip(",.!'\"") for t in name_lower.split() if len(t.strip(",.!'\"")) >= 3]
                if name_lower in query_lower or any(tok in query_lower for tok in tokens):
                    direct_cards.append(ActionCard(
                        action_id=f"direct-act-{sub.id or sub.name}",
                        title=f"Confirm Cancellation of {sub.name}",
                        description=f"Click to cancel and remove {sub.name} (₹{sub.amount:.2f}/{sub.billingCycle.value.lower()}) from your budget tracker.",
                        action_type=ActionType.CANCEL_SUBSCRIPTION,
                        target_subscription_id=sub.id,
                        target_subscription_name=sub.name,
                        payload={"action": "CANCEL_SUBSCRIPTION", "subscription_id": sub.id, "subscription_name": sub.name},
                        requires_confirmation=True,
                        confirmation_title=f"Confirm Tracker Cancellation: {sub.name}",
                        confirmation_message=(
                            f"Marking {sub.name} as cancelled will update your monthly budget and stop tracking. "
                            f"Make sure to complete the cancellation on {sub.name}'s account page as well."
                        ),
                        provider_portal_url=get_provider_portal_url(sub.name),
                        estimated_monthly_savings=sub.monthly_cost,
                        button_text=f"Confirm Cancel {sub.name}"
                    ))
            action_cards = direct_cards + action_cards



        # =========================================================================
        # 5. Retrieve Web Search & Market Citation Sources
        # =========================================================================
        collected_sources: List[WebSearchSource] = []
        seen_urls = set()

        names_to_check = [s.name.lower() for s in subscriptions]
        for key, src in VERIFIED_PROVIDER_SOURCES.items():
            if key in query_lower or any(key in n for n in names_to_check):
                if src["url"] not in seen_urls:
                    seen_urls.add(src["url"])
                    collected_sources.append(WebSearchSource(**src))

        # Optional live search fallback if no static source matched and deals/plans requested
        if not collected_sources and any(k in query_lower for k in ["plan", "price", "pricing", "deal", "discount", "alternative", "cost", "vs", "bundle"]):
            try:
                tokens = [w for w in query_lower.split() if len(w) >= 4 and w not in ["what", "give", "show", "tell", "about", "with", "this", "that", "there", "where"]]
                if tokens:
                    search_term = tokens[0]
                    live_res = await self.web_search_tool.search_subscription_deals(search_term, max_results=3)
                    for item in live_res:
                        url = item.get("url", "")
                        if url and url not in seen_urls:
                            seen_urls.add(url)
                            import urllib.parse
                            domain = urllib.parse.urlparse(url).netloc or "web"
                            collected_sources.append(WebSearchSource(
                                title=item.get("title", f"{search_term.capitalize()} Details"),
                                url=url,
                                snippet=item.get("snippet", ""),
                                domain=domain
                            ))
            except Exception as ex:
                logger.warning("Live web search fallback: %s", ex)

        sources_lines = [
            f"- [{s.title}]({s.url}): {s.snippet or s.domain}"
            for s in collected_sources
        ]
        sources_context_str = "\n".join(sources_lines) or "No external web sources queried for this prompt."

        # =========================================================================
        # 6. Synthesize Conversational Response
        # =========================================================================
        subs_context_lines = [
            f"- {s.name} ({s.category}): ₹{s.amount:.2f} / {s.billingCycle.value} (Renewal: {s.renewalDate or 'N/A'}, Status: {s.status.value})"
            for s in subscriptions
        ]
        subs_context_str = "\n".join(subs_context_lines) or "No subscriptions registered."
        agent_insights_str = "\n".join(agent_insights_parts) or "Standard conversational mode."
        history_str = self.memory.get_history_summary(session_id)
        cross_session_context = self.memory.get_cross_session_context(user_id=user_id, current_session_id=session_id)

        try:
            prompt_val = self.conversational_prompt.format_messages(
                query=sanitized_query,
                subs_context=subs_context_str,
                agent_insights=agent_insights_str,
                sources_context=sources_context_str,
                cross_session_context=cross_session_context or "None (First interaction for this user)",
                history=history_str
            )
            llm_response = await self.llm.ainvoke(prompt_val)
            synthesized_text = llm_response.content if hasattr(llm_response, "content") else str(llm_response)
        except Exception as e:
            logger.error("Error synthesizing conversational response with LLM: %s", e)
            # Safe structured conversational fallback
            synthesized_text = self._build_deterministic_fallback_response(
                query=sanitized_query,
                subscriptions=subscriptions,
                analyser_report=analyser_report,
                ranked_optimizations=ranked_optimizations,
                renewal_assessment=renewal_assessment
            )

        # =========================================================================
        # 7. Save Turn to Persistent PostgreSQL Session Memory
        # =========================================================================
        self.memory.add_user_message(session_id=session_id, message=sanitized_query, user_id=user_id, intent=detected_intent)
        self.memory.add_ai_message(session_id=session_id, message=synthesized_text, user_id=user_id, intent=detected_intent)

        # Deduplicate Action Cards by target_subscription_name + action_type
        seen_cards = set()
        deduped_cards = []
        for card in action_cards:
            key = f"{card.target_subscription_name}_{card.action_type.value}"
            if key not in seen_cards:
                seen_cards.add(key)
                deduped_cards.append(card)

        return ChatResponse(
            response=synthesized_text.strip(),
            session_id=session_id,
            intent_detected=detected_intent,
            agents_invoked=agents_invoked,
            action_cards=deduped_cards,
            sources=collected_sources,
            guardrail_status=GuardrailStatus(
                passed=True,
                domain_valid=True,
                security_valid=True,
                category="SUBSCRIPTION_QUERY"
            )
        )

    def _build_deterministic_fallback_response(
        self,
        query: str,
        subscriptions: List[SubscriptionDTO],
        analyser_report: Optional[AnalyserReport],
        ranked_optimizations: Optional[RankedOptimizations],
        renewal_assessment: Optional[RenewalRiskAssessment]
    ) -> str:
        """
        Creates a rich fallback response if LLM endpoint is temporarily unreachable.
        """
        total_spend = sum(s.monthly_cost for s in subscriptions if s.status.value == "ACTIVE")
        parts = []

        if "how much" in query.lower() or "spend" in query.lower():
            parts.append(f"You are currently spending **₹{total_spend:.2f} per month** across **{len(subscriptions)} subscriptions**.")
            by_cat = {}
            for s in subscriptions:
                by_cat[s.category] = round(by_cat.get(s.category, 0.0) + s.monthly_cost, 2)
            parts.append("### Category Breakdown:")
            for cat, amt in by_cat.items():
                parts.append(f"- **{cat}**: ₹{amt:.2f}/mo")
        elif "save" in query.lower() or "optimize" in query.lower():
            if ranked_optimizations and ranked_optimizations.recommendations:
                parts.append(f"We identified **₹{ranked_optimizations.total_potential_monthly_savings:.2f}/month** in potential savings!")
                parts.append("### Top Recommendations:")
                for r in ranked_optimizations.recommendations[:3]:
                    parts.append(f"- **{r.title}**: Save ₹{r.monthly_savings:.2f}/mo ({r.rationale})")
            else:
                parts.append("Your subscriptions are currently running at healthy efficiency.")
        elif "renew" in query.lower() or "hike" in query.lower():
            if renewal_assessment:
                parts.append(f"You have **₹{renewal_assessment.total_upcoming_30d_renewal_spend:.2f}** in scheduled renewals over the next 30 days.")
                for a in renewal_assessment.subscription_assessments[:3]:
                    parts.append(f"- **{a.subscription_name}**: Renews in {a.days_until_renewal} days (₹{a.predicted_renewal_amount:.2f}). {a.proactive_suggestion}")
            else:
                parts.append("No urgent renewals detected.")
        else:
            parts.append(f"Here is your subscription summary ({len(subscriptions)} active):")
            for s in subscriptions:
                parts.append(f"- **{s.name}**: ₹{s.amount:.2f}/{s.billingCycle.value.lower()} ({s.category})")

        return "\n".join(parts)
