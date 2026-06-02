import time
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.core.logging import logger


class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        """
        Logs incoming requests details, status codes, and execution duration.
        """
        start_time = time.time()
        
        # Log request receipt
        method = request.method
        path = request.url.path
        query = request.url.query
        full_path = f"{path}?{query}" if query else path
        
        logger.info(f"Incoming request: {method} {full_path}")
        
        try:
            response = await call_next(request)
            process_time = (time.time() - start_time) * 1000
            
            logger.info(
                f"Completed request: {method} {full_path} | "
                f"Status: {response.status_code} | "
                f"Latency: {process_time:.2f}ms"
            )
            response.headers["X-Process-Time"] = f"{process_time:.2f}ms"
            return response
        except Exception as e:
            process_time = (time.time() - start_time) * 1000
            logger.error(
                f"Request failed: {method} {full_path} | "
                f"Error: {str(e)} | "
                f"Latency: {process_time:.2f}ms",
                exc_info=True,
            )
            raise e
        
