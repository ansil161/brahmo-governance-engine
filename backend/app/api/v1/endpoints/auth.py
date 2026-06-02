from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.dependencies.database import get_db
from app.schemas.auth import LoginRequest, SupabaseAuthRequest, Token
from app.schemas.common import MessageResponse
from app.schemas.user import UserCreate, UserResponse
from app.services.auth_service import auth_service
from app.services.user_service import user_service

router = APIRouter()


@router.post("/signup", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def signup(
    *,
    db: AsyncSession = Depends(get_db),
    user_in: UserCreate,
) -> Any:
    """
    Register a new local user with email and password credentials.
    """
    db_user = await user_service.get_by_email(db, email=user_in.email)
    if db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this email address already exists.",
        )
    return await user_service.create(db, obj_in=user_in)


@router.post("/login", response_model=Token)
async def login(
    db: AsyncSession = Depends(get_db),
    form_data: OAuth2PasswordRequestForm = Depends(),
) -> Any:
    """
    OAuth2-compatible login. Yields a local JWT token for API usage.
    Useful for testing APIs directly within /docs Swagger UI.
    """
    user = await auth_service.authenticate(
        db, email=form_data.username, password=form_data.password
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect email or password",
        )
    elif not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user account",
        )

    # Local tokens store user primary key ID as 'sub' string
    access_token = create_access_token(subject=str(user.id))
    return Token(access_token=access_token)


@router.post("/login-supabase", response_model=UserResponse)
async def login_supabase(
    *,
    db: AsyncSession = Depends(get_db),
    payload: SupabaseAuthRequest,
) -> Any:
    """
    Validate a client-side Supabase JWT access token.
    Saves or synchronizes the user profile in PostgreSQL database.
    """
    user = await auth_service.authenticate_supabase_token(
        db, token=payload.access_token
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired Supabase authentication token",
        )
    return user
