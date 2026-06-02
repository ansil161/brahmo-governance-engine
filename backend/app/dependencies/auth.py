from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import MSG_FORBIDDEN, MSG_UNAUTHORIZED, ROLE_ADMIN
from app.dependencies.database import get_db
from app.models.user import User
from app.services.auth_service import auth_service
from app.services.user_service import user_service

# OAuth2PasswordBearer looks for an Authorization header with a Bearer token
reusable_oauth2 = OAuth2PasswordBearer(
    tokenUrl="api/v1/auth/login", auto_error=False
)


async def get_current_user(
    db: AsyncSession = Depends(get_db),
    token: Optional[str] = Depends(reusable_oauth2),
) -> User:
    """
    Get the current authenticated user by validating the JWT token (local or Supabase).
    """
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=MSG_UNAUTHORIZED,
            headers={"WWW-Authenticate": "Bearer"},
        )

    # First attempt to authenticate as a Supabase token
    user = await auth_service.authenticate_supabase_token(db, token=token)
    
    # If not a Supabase token, check if it's a local/native JWT
    if not user:
        from app.core.security import decode_token
        payload = decode_token(token)
        if not payload:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=MSG_UNAUTHORIZED,
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Local tokens store primary key ID in "sub"
        user_id_str = payload.get("sub")
        if not user_id_str:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=MSG_UNAUTHORIZED,
                headers={"WWW-Authenticate": "Bearer"},
            )
            
        try:
            user_id = int(user_id_str)
            user = await user_service.get_by_id(db, user_id=user_id)
        except ValueError:
            # If sub is not an int, it could be a Supabase ID (UUID string)
            user = await user_service.get_by_supabase_id(db, supabase_id=user_id_str)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=MSG_UNAUTHORIZED,
        )
    return user


def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """Ensure the authenticated user is active."""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user",
        )
    return current_user


def get_current_admin_user(
    current_user: User = Depends(get_current_active_user),
) -> User:
    """Ensure the active authenticated user has admin privileges."""
    if current_user.role != ROLE_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=MSG_FORBIDDEN,
        )
    return current_user
