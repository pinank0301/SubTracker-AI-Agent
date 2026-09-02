from typing import Generic, Optional, TypeVar, Any
# pyrefly: ignore [missing-import]
from pydantic import BaseModel, Field
from datetime import datetime, timezone

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    """
    Standardized API response envelope matching the Spring Boot platform structure.
    """
    success: bool = True
    message: str = "Operation completed successfully"
    data: Optional[T] = None
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @classmethod
    def ok(cls, data: T, message: str = "Success") -> "ApiResponse[T]":
        return cls(success=True, message=message, data=data)

    @classmethod
    def fail(cls, message: str, data: Optional[Any] = None) -> "ApiResponse[Any]":
        return cls(success=False, message=message, data=data)


class ErrorResponse(BaseModel):
    """
    Error details response.
    """
    error_code: str
    message: str
    details: Optional[Any] = None
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class HealthResponse(BaseModel):
    """
    Health check payload.
    """
    status: str = "UP"
    service: str = "ai-agent-service"
    version: str = "1.0.0"
    model: str
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

