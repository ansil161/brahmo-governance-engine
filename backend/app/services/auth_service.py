from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_token, verify_password
from app.models.user import User
from app.repositories.user_repository import user_repository
from app.schemas.user import UserCreate


class AuthService:
    async def authenticate(
        self, db: AsyncSession, *, email: str, password: str
    ) -> Optional[User]:
        """Authenticate a user using local email and password credentials."""
        user = await user_repository.get_by_email(db, email=email)
        if not user or not user.hashed_password:
            return None
        if not verify_password(password, user.hashed_password):
            return None
        return user

    async def authenticate_supabase_token(
        self, db: AsyncSession, *, token: str
    ) -> Optional[User]:
        """
        Authenticate a user using a Supabase JWT token.
        If the token is valid but the user does not exist in our database yet,
        this will automatically create a local user record.
        """
        payload = decode_token(token)
        if not payload:
            return None

        # Supabase JWT payloads store user ID under "sub" and email under "email"
        supabase_id = payload.get("sub")
        email = payload.get("email")

        if not supabase_id or not email:
            return None

        # Try to find by supabase_id first
        user = await user_repository.get_by_supabase_id(db, supabase_id)
        if not user:
            # Fallback to search by email in case of prior local registration
            user = await user_repository.get_by_email(db, email)
            if user:
                # Update existing local user with supabase_id link
                user.supabase_id = supabase_id
                db.add(user)
                await db.flush()
            else:
                # Create a new local shadow user profile linked to Supabase
                user_metadata = payload.get("user_metadata", {})
                full_name = user_metadata.get("full_name") or user_metadata.get("name")
                
                user = User(
                    email=email,
                    supabase_id=supabase_id,
                    full_name=full_name,
                    role="user",
                    is_active=True,
                )
                db.add(user)
                await db.flush()
                await db.refresh(user)

        return user


auth_service = AuthService()
