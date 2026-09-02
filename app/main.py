import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import get_settings
from app.api.router import api_router
from app.schemas.common import ApiResponse, HealthResponse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("ai_agent_service")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    logger.info("==================================================================")
    logger.info("🚀 Starting %s v%s", settings.APP_NAME, settings.APP_VERSION)
    logger.info("🤖 Primary LLM Model: %s", settings.OPENAI_MODEL_NAME)
    logger.info("🔗 Base URL: %s", settings.OPENAI_API_BASE)
    logger.info("🛡️ Guardrail Strict Domain Mode: %s", settings.GUARDRAIL_STRICT_DOMAIN_MODE)
    logger.info("==================================================================")
    yield
    logger.info("🛑 Shutting down AI Agent Service...")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description=(
            "Enterprise Multi-Agent AI Service for Subscription Analysis, Optimization, "
            "Renewal Prediction, and Conversational Management powered by LangChain and Capgemini Generative AI."
        ),
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json"
    )

    # =========================================================================
    # CORS Configuration (Eliminates all cross-origin issues)
    # =========================================================================
    origins = settings.CORS_ORIGINS if isinstance(settings.CORS_ORIGINS, list) else ["*"]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins if origins != ["*"] else ["*"],
        allow_credentials=True if origins != ["*"] else False,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["*"]
    )

    # =========================================================================
    # Global Exception Handlers for Unified API Responses
    # =========================================================================
    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content=ApiResponse.fail(
                message=str(exc.detail),
                data={"status_code": exc.status_code}
            ).model_dump()
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=ApiResponse.fail(
                message="Request Validation Error",
                data={"errors": exc.errors()}
            ).model_dump()
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception):
        logger.error("Unhandled Exception: %s", exc, exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ApiResponse.fail(
                message=f"Internal Server Error: {str(exc)}",
                data=None
            ).model_dump()
        )

    # =========================================================================
    # Health and Info Endpoints
    # =========================================================================
    @app.get("/", tags=["Health"])
    async def root():
        return ApiResponse.ok(
            data={"status": "UP", "service": settings.APP_NAME, "docs": "/docs"},
            message="Subscription Multi-Agent AI Service is running"
        )

    # =========================================================================
    # Minimal Health-Check for External Uptime Monitoring (e.g. UptimeRobot)
    # This endpoint is intentionally ultra-lightweight: no DB, no AI, no auth.
    # Suitable for pinging every 5 minutes to keep the Render service alive.
    # =========================================================================
    @app.get("/health", tags=["Health"])
    async def health_ping():
        return {"status": "ok"}

    # Detailed internal health check (includes service metadata)
    @app.get("/api/ai/health", response_model=ApiResponse[HealthResponse], tags=["Health"])
    async def health_check():
        return ApiResponse.ok(
            data=HealthResponse(
                status="UP",
                service=settings.APP_NAME,
                version=settings.APP_VERSION,
                model=settings.OPENAI_MODEL_NAME
            ),
            message="Health check passed"
        )

    # Include API router
    app.include_router(api_router)

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        reload=settings.DEBUG
    )
