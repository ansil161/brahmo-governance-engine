from app.core.database import get_db

# Re-exporting database session dependency for router use
__all__ = ["get_db"]
