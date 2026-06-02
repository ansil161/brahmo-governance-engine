import asyncio
from app.core.logging import logger
from app.workers.tasks import perform_database_cleanup_task


class PeriodicScheduler:
    def __init__(self):
        self._running = False
        self._task = None

    async def start(self) -> None:
        """Start the periodic task scheduler loop."""
        if self._running:
            return
        
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info("Background task scheduler started.")

    async def stop(self) -> None:
        """Stop the scheduler loop and wait for active tasks to close."""
        if not self._running:
            return
        
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Background task scheduler stopped.")

    async def _loop(self) -> None:
        """Internal loop executing scheduled tasks at intervals."""
        while self._running:
            try:
                # Run cleanup every 1 hour (3600 seconds)
                # For development/demonstration, we set a smaller duration or check condition
                await perform_database_cleanup_task()
                await asyncio.sleep(3600)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in scheduler execution loop: {str(e)}", exc_info=True)
                await asyncio.sleep(60)  # Sleep on exception to avoid tight loops


scheduler = PeriodicScheduler()
