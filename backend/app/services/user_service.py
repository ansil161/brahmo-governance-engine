from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_password_hash
from app.models.user import User
from app.repositories.user_repository import user_repository
from app.schemas.user import UserCreate, UserUpdate


class UserService:
    async def get_by_id(self, db: AsyncSession, user_id: int) -> Optional[User]:
        """Retrieve a user by their database primary key."""
        return await user_repository.get(db, id=user_id)

    async def get_by_email(self, db: AsyncSession, email: str) -> Optional[User]:
        """Retrieve a user by their email address."""
        return await user_repository.get_by_email(db, email=email)

    async def get_by_supabase_id(
        self, db: AsyncSession, supabase_id: str
    ) -> Optional[User]:
        """Retrieve a user by their Supabase user ID."""
        return await user_repository.get_by_supabase_id(db, supabase_id=supabase_id)

    async def get_multi(
        self, db: AsyncSession, *, skip: int = 0, limit: int = 100
    ) -> List[User]:
        """Retrieve multiple users."""
        return await user_repository.get_multi(db, skip=skip, limit=limit)

    async def count_users(self, db: AsyncSession) -> int:
        """Count total user records."""
        return await user_repository.count(db)

    async def create(self, db: AsyncSession, *, obj_in: UserCreate) -> User:
        """Create a user with hashed password."""
        # Convert password to hash
        hashed_password = get_password_hash(obj_in.password)
        
        # Prepare data model ignoring the raw password
        db_obj = User(
            email=obj_in.email,
            hashed_password=hashed_password,
            full_name=obj_in.full_name,
            role=obj_in.role or "user",
            is_active=obj_in.is_active if obj_in.is_active is not None else True,
        )
        db.add(db_obj)
        await db.flush()
        await db.refresh(db_obj)
        return db_obj

    async def update(
        self, db: AsyncSession, *, db_obj: User, obj_in: UserUpdate
    ) -> User:
        """Update a user's details, hashing new password if provided."""
        update_data = obj_in.model_dump(exclude_unset=True)
        if "password" in update_data and update_data["password"]:
            hashed_password = get_password_hash(update_data["password"])
            update_data["hashed_password"] = hashed_password
            del update_data["password"]
            
        return await user_repository.update(db, db_obj=db_obj, obj_in=update_data)

    async def remove(self, db: AsyncSession, *, user_id: int) -> Optional[User]:
        """Remove a user by their database ID."""
        return await user_repository.remove(db, id=user_id)


user_service = UserService()
