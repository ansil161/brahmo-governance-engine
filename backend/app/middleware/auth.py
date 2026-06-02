from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.core.database import AsyncSessionLocal
from app.dependencies.auth import get_current_user


class AuthenticationMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        """
        Global middleware to inject user information into request.state.user
        if a valid authorization header is present.
        """
        request.state.user = None
        auth_header = request.headers.get("Authorization")
        
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
            async with AsyncSessionLocal() as db:
                try:
                    # Leverage dependency logic to find user
                    from fastapi import Depends
                    user = await get_current_user(db=db, token=token)
                    request.state.user = user
                except Exception:
                    # Ignore auth errors globally in middleware so public endpoints still work
                    pass

        response = await call_next(request)
        return response
