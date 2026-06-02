from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.repositories.base import BaseRepository
from app.schemas.user import UserCreate, UserUpdate


class UserRepository(BaseRepository[User, UserCreate, UserUpdate]):
    async def get_by_email(self, db: AsyncSession, email: str) -> Optional[User]:
        """Fetch a user by their email address."""
        result = await db.execute(select(self.model).filter(self.model.email == email))
        return result.scalars().first()

    async def get_by_supabase_id(
        self, db: AsyncSession, supabase_id: str
    ) -> Optional[User]:
        """Fetch a user by their Supabase UUID."""
        result = await db.execute(
            select(self.model).filter(self.model.supabase_id == supabase_id)
        )
        return result.scalars().first()


user_repository = UserRepository(User)
