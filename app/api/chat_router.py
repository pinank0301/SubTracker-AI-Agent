import logging
from fastapi import APIRouter, Depends, Header, HTTPException, status
from typing import Optional
from app.schemas.common import ApiResponse
from app.schemas.chat import (
    ChatRequest,
    ChatResponse,
    ActionExecutionRequest,
    ActionExecutionResponse
)
from app.agents.orchestrator import ConversationalOrchestratorAgent
from app.agents.memory.session_memory import get_session_memory
from app.services.action_service import ActionExecutionService, get_action_service
from app.api.dependencies import get_orchestrator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["Conversational AI Orchestrator"])


@router.post("", response_model=ApiResponse[ChatResponse])
async def chat_with_agent(
    request: ChatRequest,
    x_user_id: Optional[str] = Header(None, alias="X-User-Id"),
    orchestrator: ConversationalOrchestratorAgent = Depends(get_orchestrator)
):
    """
    Main Conversational AI Agent & Master Orchestrator Endpoint.
    - Applies LangChain domain boundary & security guardrails.
    - Classifies intent and dynamically calls specialized worker agents (Analyser, Optimizer, Renewal).
    - Synthesizes clear conversational responses and returns one-click UI action cards.
    """
    if x_user_id and not request.user_id:
        request.user_id = x_user_id

    try:
        response = await orchestrator.process_chat(request)
        return ApiResponse.ok(data=response, message="Agent conversation turn processed successfully")
    except Exception as e:
        logger.error("Chat orchestrator processing failed: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Conversational Agent processing error: {str(e)}"
        )


@router.post("/actions/execute", response_model=ApiResponse[ActionExecutionResponse])
async def execute_action_card(
    request: ActionExecutionRequest,
    x_user_id: Optional[str] = Header(None, alias="X-User-Id"),
    action_service: ActionExecutionService = Depends(get_action_service)
):
    """
    Executes a one-click action triggered from an ActionCard in the chat UI
    (e.g., Cancel subscription, Switch tier, Set renewal reminder).
    """
    if x_user_id and not request.user_id:
        request.user_id = x_user_id

    try:
        result = await action_service.execute_action(request)
        return ApiResponse.ok(data=result, message="Action processed")
    except Exception as e:
        logger.error("Failed to execute action: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Action execution error: {str(e)}"
        )


@router.get("/history/{session_id}", response_model=ApiResponse[str])
async def get_session_history(session_id: str):
    """
    Retrieves the conversation history for a given session.
    """
    memory = get_session_memory()
    history = memory.get_history_summary(session_id)
    return ApiResponse.ok(data=history, message="Session history retrieved")


@router.delete("/history/{session_id}", response_model=ApiResponse[bool])
async def clear_session_history(session_id: str):
    """
    Clears the conversation history for a session.
    """
    memory = get_session_memory()
    cleared = memory.clear_session(session_id)
    return ApiResponse.ok(data=cleared, message=f"Session {session_id} memory cleared")
