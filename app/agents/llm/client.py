import logging
from typing import Optional, List, Any
from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from app.config import get_settings

logger = logging.getLogger(__name__)


class LLMClient:
    """
    Wrapper around LangChain ChatOpenAI configured for Cloudflare Workers AI
    (OpenAI-compatible endpoint: https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/ai/v1).
    """
    def __init__(self, model_name: Optional[str] = None, temperature: Optional[float] = None):
        settings = get_settings()
        self.model_name = model_name or settings.OPENAI_MODEL_NAME
        self.temperature = temperature if temperature is not None else settings.OPENAI_TEMPERATURE
        self.api_key = settings.OPENAI_API_KEY
        self.base_url = settings.OPENAI_API_BASE.rstrip("/")

        # Cloudflare Workers AI base URL already ends in /v1, so don't append it again.
        # For other providers that need /v1 appended, check and add only if missing.
        formatted_base_url = self.base_url
        if not (formatted_base_url.endswith("/v1") or formatted_base_url.endswith("/v1/")):
            formatted_base_url = f"{formatted_base_url}/v1"
            
        logger.info(
            "Initializing LLMClient with model: %s, base_url: %s",
            self.model_name,
            formatted_base_url
        )

        try:
            self._llm = ChatOpenAI(
                model=self.model_name,
                api_key=self.api_key,
                base_url=formatted_base_url,
                temperature=self.temperature,
                max_tokens=settings.OPENAI_MAX_TOKENS,
                timeout=settings.OPENAI_REQUEST_TIMEOUT,
                max_retries=2
            )
        except Exception as e:
            logger.warning("Failed to initialize ChatOpenAI with /v1, trying raw base_url: %s", e)
            self._llm = ChatOpenAI(
                model=self.model_name,
                api_key=self.api_key,
                base_url=self.base_url,
                temperature=self.temperature,
                max_tokens=settings.OPENAI_MAX_TOKENS,
                timeout=settings.OPENAI_REQUEST_TIMEOUT,
                max_retries=2
            )

    @property
    def llm(self) -> ChatOpenAI:
        return self._llm

    async def ainvoke_safe(
        self,
        messages: List[BaseMessage],
        fallback_text: Optional[str] = None
    ) -> str:
        """
        Safely invokes the LLM with error handling and fallback text.
        """
        try:
            response = await self._llm.ainvoke(messages)
            if hasattr(response, "content"):
                return str(response.content)
            return str(response)
        except Exception as e:
            logger.error("LLM ainvoke encountered an error: %s", e)
            if fallback_text:
                return fallback_text
            raise e


def get_chat_llm(model_name: Optional[str] = None, temperature: Optional[float] = None) -> ChatOpenAI:
    """
    Factory function providing a LangChain ChatOpenAI instance.
    """
    client = LLMClient(model_name=model_name, temperature=temperature)
    return client.llm
