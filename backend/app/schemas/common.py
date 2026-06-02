from typing import Any, Generic, List, TypeVar
from pydantic import BaseModel

T = TypeVar("T")


class MessageResponse(BaseModel):
    message: str


class HealthCheck(BaseModel):
    status: str
    environment: str
    database: str


class PageParams(BaseModel):
    page: int = 1
    size: int = 50


class PaginatedResponse(BaseModel, Generic[T]):
    items: List[T]
    total: int
    page: int
    size: int
    pages: int
