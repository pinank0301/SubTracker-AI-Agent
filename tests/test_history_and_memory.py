# pyrefly: ignore [missing-import]
import pytest
from app.agents.memory.session_memory import PersistentSessionMemory, get_session_memory
# pyrefly: ignore [missing-import]
from fastapi.testclient import TestClient
from app.main import app

# Uses the same local PostgreSQL instance with the subtracker database.
# Tests use unique session/user IDs to avoid collisions.
TEST_DATABASE_URL = "postgresql://postgres:root@localhost:5432/subtracker"


def test_persistent_memory_storage():
    memory = PersistentSessionMemory(database_url=TEST_DATABASE_URL)

    user_id = "test-user-memory-abc"
    session_id = "test-sess-memory-123"

    # Clean up any previous test data
    memory.clear_session(session_id)

    memory.add_user_message(session_id=session_id, message="How much do I spend on Netflix?", user_id=user_id, intent="ANALYSE")
    memory.add_ai_message(session_id=session_id, message="You spend $22.99/mo on Netflix.", user_id=user_id, intent="ANALYSE")

    # Verify session messages
    messages = memory.get_messages(session_id)
    assert len(messages) == 2
    assert messages[0].content == "How much do I spend on Netflix?"
    assert messages[1].content == "You spend $22.99/mo on Netflix."

    # Verify full history
    full_history = memory.get_session_full_history(session_id)
    assert len(full_history) == 2
    assert full_history[0]["user_id"] == user_id
    assert full_history[0]["intent"] == "ANALYSE"

    # Verify user sessions list
    sessions = memory.get_user_sessions(user_id)
    assert len(sessions) >= 1
    matching = [s for s in sessions if s["session_id"] == session_id]
    assert len(matching) == 1
    assert matching[0]["message_count"] == 2

    # Verify cross-session context when starting a new session
    new_session_id = "test-sess-memory-456"
    cross_context = memory.get_cross_session_context(user_id=user_id, current_session_id=new_session_id)
    assert "How much do I spend on Netflix?" in cross_context

    # Cleanup
    memory.clear_session(session_id)


def test_history_api_endpoints():
    client = TestClient(app)
    memory = PersistentSessionMemory(database_url=TEST_DATABASE_URL)

    import app.api.history as history_module
    original_fn = history_module.get_session_memory

    # Monkeypatch get_session_memory for the history module
    history_module.get_session_memory = lambda: memory

    user_id = "test-user-api-hist"
    session_id = "test-sess-api-hist-01"

    # Clean up any previous test data
    memory.clear_session(session_id)

    memory.add_user_message(session_id=session_id, message="Can I save money on Spotify?", user_id=user_id)
    memory.add_ai_message(session_id=session_id, message="Yes, switch to the annual plan to save 17%.", user_id=user_id)

    try:
        # 1. Fetch user sessions
        res = client.get(f"/api/ai/history/user/{user_id}")
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert len(data["data"]) >= 1

        # 2. Fetch session details
        res = client.get(f"/api/ai/history/session/{session_id}")
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert len(data["data"]) == 2

        # 3. Delete session
        res = client.delete(f"/api/ai/history/session/{session_id}")
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
    finally:
        # Restore original function and cleanup
        history_module.get_session_memory = original_fn
        memory.clear_session(session_id)
