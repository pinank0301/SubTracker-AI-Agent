# pyrefly: ignore [missing-import]
from fastapi import APIRouter
from app.api.chat_router import router as chat_router
from app.api.analyser_router import router as analyser_router
from app.api.optimizer_router import router as optimizer_router
from app.api.renewal_router import router as renewal_router
from app.api.history import router as history_router

api_router = APIRouter(prefix="/api/ai")

api_router.include_router(chat_router)
api_router.include_router(analyser_router)
api_router.include_router(optimizer_router)
api_router.include_router(renewal_router)
api_router.include_router(history_router)

