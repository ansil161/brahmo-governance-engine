import asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal, engine
from app.core.security import get_password_hash
from app.models.base import Base
from app.models.user import User


async def seed_data() -> None:
    print("Initializing database seeding...")
    
    # 1. Create tables if they do not exist
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
    # 2. Seed data
    async with AsyncSessionLocal() as db:
        # Check if users already exist
        from sqlalchemy import select
        result = await db.execute(select(User))
        if len(result.scalars().all()) > 0:
            print("Database already contains user records. Skipping seeding.")
            return

        print("Creating default admin account...")
        admin_user = User(
            email="admin@healthscore.com",
            hashed_password=get_password_hash("AdminPass123!"),
            full_name="System Administrator",
            role="admin",
            is_active=True,
        )
        db.add(admin_user)

        print("Creating default user account...")
        standard_user = User(
            email="user@healthscore.com",
            hashed_password=get_password_hash("UserPass123!"),
            full_name="John Doe",
            role="user",
            is_active=True,
        )
        db.add(standard_user)

        await db.commit()
        print("Database seeding completed successfully.")


if __name__ == "__main__":
    asyncio.run(seed_data())
