from contextlib import asynccontextmanager
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.database import engine
from app.core.logging import logger, setup_logging
from app.middleware.logging import LoggingMiddleware
from app.middleware.rate_limit import RateLimitMiddleware
from app.models.base import Base
from app.workers.scheduler import scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Initialize logging
    setup_logging()
    logger.info("Initializing application services...")

    # 2. Database table auto-creation for quickstart (especially SQLite)
    try:
        async with engine.begin() as conn:
            logger.info("Verifying/creating database tables...")
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database verification complete.")
    except Exception as e:
        logger.error(f"Failed to auto-create database tables: {str(e)}", exc_info=True)

    # 3. Start background task scheduler
    await scheduler.start()

    yield

    # 4. Clean up and stop background task scheduler on shutdown
    logger.info("Shutting down application services...")
    await scheduler.stop()


# Create FastAPI application
app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Backend API for HealthScore dashboard and user/system operations.",
    version="1.0.0",
    lifespan=lifespan,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Set up CORS middleware
if settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin) for origin in settings.BACKEND_CORS_ORIGINS],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Add custom middlewares (order matters: rate limit first, then logging)
app.add_middleware(RateLimitMiddleware, limit_per_minute=60)
app.add_middleware(LoggingMiddleware)

# Include main router
app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/")
async def root():
    """Root redirect message."""
    return {
        "message": f"Welcome to {settings.PROJECT_NAME} API.",
        "docs_url": "/docs",
        "health_check": f"{settings.API_V1_STR}/health",
    }


@app.post("/api/nodes/{node_id}/supersede", status_code=200)
async def supersede_node(
    node_id: str,
    actor_id: str = Query(..., description="The user or system ID triggering this action"),
    max_depth: int = Query(3, ge=1, le=10, description="Max depth of child invalidation traversal"),
):
    """
    Supersede a target knowledge node and run the cascade invalidation engine to mark
    downstream derived children as REVIEW_REQUIRED.
    """
    from fastapi import Query, HTTPException, status
    from governance.cascade_engine import run_cascade, supabase

    # 1. Fetch current status of target node
    try:
        response = supabase.table("knowledge_nodes").select("status").eq("id", node_id).execute()
        nodes = response.data
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error during lookup: {str(e)}"
        )

    if not nodes:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Knowledge node {node_id} not found."
        )

    current_status = nodes[0].get("status")

    # Guard: Legal Hold prevents superseding
    if current_status == "LEGAL_HOLD":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot supersede a node under LEGAL_HOLD."
        )

    # 2. Update node status to SUPERSEDED (if not already)
    if current_status != "SUPERSEDED":
        try:
            # Update status
            supabase.table("knowledge_nodes").update(
                {"status": "SUPERSEDED"}
            ).eq("id", node_id).execute()

            # Insert status change audit log
            supabase.table("audit_log").insert({
                "node_id": node_id,
                "actor_id": actor_id,
                "action": "STATUS_CHANGE",
                "old_value": current_status,
                "new_value": "SUPERSEDED",
            }).execute()
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to update node status or audit log: {str(e)}"
            )

    # 3. Run cascade invalidation engine
    try:
        cascade_summary = run_cascade(
            superseded_node_id=node_id,
            actor_id=actor_id,
            max_depth=max_depth
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Cascade invalidation engine failed: {str(e)}"
        )

    # 4. Route pulse alerts for affected nodes
    try:
        from governance.pulse_router import route_pulse_alerts
        affected_node_ids = [n["node_id"] for n in cascade_summary.get("affected_nodes", [])]
        pulse_summary = route_pulse_alerts(affected_node_ids)
    except Exception as e:
        # Log error but do not fail the request since cascade invalidation succeeded
        logger.error(f"Pulse alert notification routing failed: {str(e)}", exc_info=True)
        pulse_summary = {"status": "error", "message": str(e), "alerts_created": 0}

    return {
        "message": "Node successfully superseded and cascade invalidation run.",
        "cascade_summary": cascade_summary,
        "pulse_summary": pulse_summary
    }


@app.get("/api/health-score/{org_id}", status_code=200)
async def get_health_score(org_id: str):
    """
    Retrieve the 4-dimension Knowledge Health Score (Coverage, Freshness, Consistency, Balance, and Overall)
    for the specified organization ID.
    """
    from fastapi import HTTPException, status
    from governance.health_score import compute_health_score

    try:
        score_data = compute_health_score(org_id)
        return score_data
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to calculate knowledge health score: {str(e)}"
        )
