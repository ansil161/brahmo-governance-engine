import asyncio
from app.core.logging import logger


async def send_verification_email_task(email: str, token: str) -> None:
    """
    Background task to send verification emails.
    Can be run via FastAPI BackgroundTasks.
    """
    logger.info(f"Starting email dispatch task to {email}...")
    # Simulate network delay for SMTP connection
    await asyncio.sleep(2)
    logger.info(f"Verification email successfully sent to {email} with token {token[:10]}...")


async def perform_database_cleanup_task() -> None:
    """
    Background task for periodic cleanups (e.g. expired tokens, rate limit traces).
    """
    logger.info("Starting background database cleanup...")
    # Simulate DB cleanup query latency
    await asyncio.sleep(1)
    logger.info("Database cleanup completed successfully.")
