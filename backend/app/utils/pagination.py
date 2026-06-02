import math
from typing import Type, TypeVar
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import Base
from app.schemas.common import PaginatedResponse

ModelType = TypeVar("ModelType", bound=Base)
SchemaType = TypeVar("SchemaType", bound=BaseModel)


async def paginate(
    db: AsyncSession,
    stmt: select,
    model: Type[ModelType],
    page: int = 1,
    size: int = 50,
) -> PaginatedResponse:
    """
    Paginate a select statement asynchronously.
    """
    if page < 1:
        page = 1
    if size < 1:
        size = 1

    # 1. Calculate count
    count_stmt = select(func.count()).select_from(stmt.subquery())
    count_result = await db.execute(count_stmt)
    total = count_result.scalar() or 0

    # 2. Add offset and limit to original select
    offset = (page - 1) * size
    paginated_stmt = stmt.offset(offset).limit(size)
    
    result = await db.execute(paginated_stmt)
    items = list(result.scalars().all())

    # 3. Calculate pages count
    pages = math.ceil(total / size) if total > 0 else 0

    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        size=size,
        pages=pages,
    )
