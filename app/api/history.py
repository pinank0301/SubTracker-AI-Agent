import logging
from typing import List, Dict, Any, Optional
# pyrefly: ignore [missing-import]
from fastapi import APIRouter, Path, HTTPException
from app.agents.memory.session_memory import get_session_memory
from app.schemas.common import ApiResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/history", tags=["Conversation History"])


@router.get("/user/{user_id}", response_model=ApiResponse[List[Dict[str, Any]]])
async def get_user_chat_sessions(
    user_id: str = Path(..., description="User ID to retrieve past chat sessions for")
):
    """
    Retrieve all conversation sessions and message counts for a user.
    Enables cross-session history tracking and user revisit detection.
    """
    memory = get_session_memory()
    sessions = memory.get_user_sessions(user_id)
    return ApiResponse(
        data=sessions,
        message=f"Retrieved {len(sessions)} conversation sessions for user {user_id}"
    )


@router.get("/session/{session_id}", response_model=ApiResponse[List[Dict[str, Any]]])
async def get_session_messages(
    session_id: str = Path(..., description="Session ID to retrieve message history for")
):
    """
    Retrieve the full chronological message trail for a specific conversation session.
    """
    memory = get_session_memory()
    messages = memory.get_session_full_history(session_id)
    if not messages:
        raise HTTPException(status_code=404, detail="No conversation history found for this session ID.")
    
    return ApiResponse(
        data=messages,
        message=f"Retrieved {len(messages)} messages for session {session_id}"
    )


@router.delete("/session/{session_id}", response_model=ApiResponse[Dict[str, Any]])
async def clear_session_history(
    session_id: str = Path(..., description="Session ID to clear")
):
    """
    Delete all stored messages for a specific session.
    """
    memory = get_session_memory()
    success = memory.clear_session(session_id)
    return ApiResponse(
        data={"cleared": success, "session_id": session_id},
        message="Session conversation history deleted successfully"
    )
