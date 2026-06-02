import time
from typing import Dict, List
from fastapi import status
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.constants import RATE_LIMIT_DEFAULT_LIMIT


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, limit_per_minute: int = RATE_LIMIT_DEFAULT_LIMIT):
        super().__init__(app)
        self.limit_per_minute = limit_per_minute
        # Dictionary storing IP as key and list of request timestamps as values
        self.request_history: Dict[str, List[float]] = {}

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        """
        Sliding-window rate limiter utilizing user IP address.
        """
        client_ip = request.client.host if request.client else "unknown"
        
        # Bypass rate limit for local test requests if necessary (or keep simple)
        if client_ip == "testclient":
            return await call_next(request)
            
        current_time = time.time()
        
        # Initialize or retrieve timestamps for IP
        timestamps = self.request_history.get(client_ip, [])
        
        # Filter timestamps within the last 60 seconds
        timestamps = [t for t in timestamps if current_time - t < 60]
        
        # Check rate limit
        if len(timestamps) >= self.limit_per_minute:
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={"detail": "Too many requests. Please try again later."},
            )
            
        # Record new timestamp and update state
        timestamps.append(current_time)
        self.request_history[client_ip] = timestamps
        
        return await call_next(request)
