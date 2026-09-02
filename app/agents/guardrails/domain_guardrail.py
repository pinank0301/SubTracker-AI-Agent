import logging
from typing import Tuple, Dict, Any, Optional
# pyrefly: ignore [missing-import]
from langchain_core.prompts import ChatPromptTemplate
# pyrefly: ignore [missing-import]
from langchain_core.messages import SystemMessage, HumanMessage
from app.agents.llm.client import get_chat_llm
from app.config import get_settings

logger = logging.getLogger(__name__)


class DomainGuardrail:
    """
    Advanced LangChain Domain Guardrail that enforces strict domain boundaries,
    ensuring the agent only processes queries related to Subscription Management,
    Billing, Spend Analysis, Plan Optimization, and Renewal Predictions.
    """

    # Domain vocabulary for fast heuristics
    IN_DOMAIN_KEYWORDS = [
        "sub", "subs", "subscription", "subscriptions", "bill", "billing", "invoice", "cost", "spend",
        "spending", "plan", "plans", "tier", "renew", "renewal", "renewals", "cancel", "cancellation",
        "downgrade", "upgrade", "switch", "bundle", "discount", "price", "netflix", "spotify", "gym",
        "disney", "youtube", "amazon", "prime", "aws", "chatgpt", "apple", "icloud", "hulu", "saas",
        "membership", "charge", "payment", "cycle", "monthly", "annual", "yearly", "save", "saving",
        "savings", "expense", "expenses", "cheaper", "expensive", "usage", "dormant", "underused",
        "overprice", "price hike", "prediction", "forecast", "alert", "reminder", "pause", "resume"
    ]

    OUT_OF_DOMAIN_RESPONSE = (
        "I am your dedicated **Subscription & Billing AI Assistant**. "
        "I can only assist with managing, analyzing, optimizing, or predicting renewals "
        "for your subscriptions (such as streaming platforms, SaaS tools, gym memberships, "
        "and recurring billing).\n\n"
        "Here are a few things you can ask me:\n"
        "- *'How much do I spend on streaming each month?'*\n"
        "- *'Which subscriptions are under-utilized?'*\n"
        "- *'Can you help me find cheaper plan options for Netflix or Spotify?'*\n"
        "- *'Are there any upcoming renewals or price hikes this month?'*\n"
        "- *'Cancel my unused gym subscription.'*"
    )

    def __init__(self):
        self.settings = get_settings()
        self.llm = get_chat_llm(temperature=0.0)

        self.classification_prompt = ChatPromptTemplate.from_messages([
            ("system", (
                "You are a strict Domain Boundary Guardrail Classifier for a Subscription Management Platform.\n"
                "Your task is to classify whether a user query is IN_DOMAIN or OUT_OF_DOMAIN.\n\n"
                "IN_DOMAIN queries include:\n"
                "- Asking about subscription costs, categories, usage, or spending\n"
                "- Asking for plan recommendations, downgrades, upgrades, bundling, or discounts\n"
                "- Asking about renewals, billing dates, price hikes, or renewal risk\n"
                "- Asking to cancel, pause, resume, or modify subscriptions\n"
                "- General greetings or platform capability questions (e.g. 'Hello', 'What can you do?')\n\n"
                "OUT_OF_DOMAIN queries include:\n"
                "- General programming/coding questions unrelated to this platform\n"
                "- General knowledge, history, geography, weather, sports, politics, recipes, medical advice\n"
                "- Writing essays, poems, creative fiction, general translations\n\n"
                "Reply ONLY in the following format:\n"
                "DOMAIN: [IN_DOMAIN or OUT_OF_DOMAIN]\n"
                "INTENT: [ANALYSE, OPTIMIZE, RENEWAL, ACTION, GENERAL_QA, or OUT_OF_DOMAIN]\n"
                "REASON: [Brief 1 sentence reason]"
            )),
            ("human", "User Query: {query}")
        ])

    def fast_heuristic_check(self, query: str) -> Optional[bool]:
        """
        Fast heuristic check to bypass LLM latency for obvious queries.
        Returns:
            True if clearly in-domain,
            False if clearly out-of-domain (e.g. math/code/weather queries without sub keywords),
            None if ambiguous and needs LLM evaluation.
        """
        lower = query.lower().strip()
        words = lower.split()

        # Greetings & capabilities are in-domain
        if lower in ["hi", "hello", "hey", "help", "who are you", "what can you do", "menu"]:
            return True

        # Check for presence of domain keywords
        has_domain_word = any(kw in lower for kw in self.IN_DOMAIN_KEYWORDS)
        if has_domain_word:
            return True

        # Obvious off-topic queries without any subscription context
        off_topic_indicators = [
            "write a python", "write code", "calculate ", "who is ", "what is the capital",
            "weather in", "translate ", "recipe for", "tell a joke", "who won the",
            "solve this equation", "write an essay"
        ]
        if any(ind in lower for ind in off_topic_indicators) and not has_domain_word:
            return False

        # If very short single generic word without sub context
        if len(words) <= 2 and not has_domain_word:
            return False

        return None

    async def validate_domain(self, query: str) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Validates if query belongs to the Subscription platform domain.
        Returns: (is_in_domain: bool, intent: str, metadata: dict)
        """
        if not self.settings.GUARDRAIL_STRICT_DOMAIN_MODE:
            return True, "GENERAL_QA", {"guardrail_mode": "disabled"}

        # 1. Fast heuristic path
        heuristic = self.fast_heuristic_check(query)
        if heuristic is True:
            # Determine basic intent
            lower = query.lower()
            intent = "GENERAL_QA"
            if any(k in lower for k in ["cancel", "pause", "switch", "downgrade", "apply"]):
                intent = "ACTION"
            elif any(k in lower for k in ["renew", "renewal", "hike", "price hike", "upcoming"]):
                intent = "RENEWAL"
            elif any(k in lower for k in ["save", "saving", "optimize", "cheaper", "bundle", "discount"]):
                intent = "OPTIMIZE"
            elif any(k in lower for k in ["spend", "spending", "cost", "usage", "analyse", "analyze", "breakdown"]):
                intent = "ANALYSE"
            return True, intent, {"method": "fast_heuristic"}
        elif heuristic is False:
            return False, "OUT_OF_DOMAIN", {"method": "fast_heuristic_rejected"}

        # 2. LLM-based boundary validation
        try:
            prompt_val = self.classification_prompt.format_messages(query=query)
            response = await self.llm.ainvoke(prompt_val)
            content = response.content if hasattr(response, "content") else str(response)

            is_in_domain = "DOMAIN: IN_DOMAIN" in content.upper() or "IN_DOMAIN" in content.upper()
            
            # Extract intent
            intent = "GENERAL_QA"
            for possible_intent in ["ANALYSE", "OPTIMIZE", "RENEWAL", "ACTION", "GENERAL_QA"]:
                if f"INTENT: {possible_intent}" in content.upper() or possible_intent in content.upper():
                    intent = possible_intent
                    break

            if not is_in_domain:
                intent = "OUT_OF_DOMAIN"

            return is_in_domain, intent, {
                "method": "llm_guardrail",
                "raw_response": content
            }
        except Exception as e:
            logger.error("Domain Guardrail LLM evaluation error: %s", e)
            # Safe fallback: if domain keywords matched, allow; else reject
            fallback_allow = any(kw in query.lower() for kw in self.IN_DOMAIN_KEYWORDS)
            return fallback_allow, "GENERAL_QA" if fallback_allow else "OUT_OF_DOMAIN", {"error": str(e)}
