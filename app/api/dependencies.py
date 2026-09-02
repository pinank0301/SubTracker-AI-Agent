from app.agents.orchestrator import ConversationalOrchestratorAgent
from app.agents.analyser_agent import SubscriptionAnalyserAgent
from app.agents.optimizer_agent import SubscriptionOptimizerAgent
from app.agents.renewal_agent import RenewalPredictionAgent
from app.agents.tools.subscription_client import SubscriptionServiceClient, get_subscription_client
from app.services.action_service import ActionExecutionService, get_action_service

_orchestrator_instance = None
_analyser_instance = None
_optimizer_instance = None
_renewal_instance = None


def get_orchestrator() -> ConversationalOrchestratorAgent:
    global _orchestrator_instance
    if _orchestrator_instance is None:
        _orchestrator_instance = ConversationalOrchestratorAgent()
    return _orchestrator_instance


def get_analyser() -> SubscriptionAnalyserAgent:
    global _analyser_instance
    if _analyser_instance is None:
        _analyser_instance = SubscriptionAnalyserAgent()
    return _analyser_instance


def get_optimizer() -> SubscriptionOptimizerAgent:
    global _optimizer_instance
    if _optimizer_instance is None:
        _optimizer_instance = SubscriptionOptimizerAgent()
    return _optimizer_instance


def get_renewal_agent() -> RenewalPredictionAgent:
    global _renewal_instance
    if _renewal_instance is None:
        _renewal_instance = RenewalPredictionAgent()
    return _renewal_instance
