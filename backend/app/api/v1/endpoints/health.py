from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.dependencies.database import get_db
from app.schemas.common import HealthCheck

router = APIRouter()


@router.get("", response_model=HealthCheck)
async def check_health(db: AsyncSession = Depends(get_db)):
    """
    Perform a system health check. Checks application settings and active db connection.
    """
    db_status = "healthy"
    try:
        # Perform a fast select query to test database connection status
        await db.execute(text("SELECT 1"))
    except Exception:
        db_status = "unhealthy"

    return HealthCheck(
        status="healthy" if db_status == "healthy" else "degraded",
        environment=settings.ENVIRONMENT,
        database=db_status,
    )
