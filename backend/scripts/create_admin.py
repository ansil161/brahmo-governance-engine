import asyncio
import sys
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal, engine
from app.core.security import get_password_hash
from app.models.base import Base
from app.models.user import User


async def create_admin(email: str, password: str) -> None:
    # Ensure tables are built
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
    async with AsyncSessionLocal() as db:
        # Check if user already exists
        result = await db.execute(select(User).filter(User.email == email))
        user = result.scalars().first()
        
        if user:
            print(f"Error: User with email {email} already exists.")
            sys.exit(1)
            
        admin_user = User(
            email=email,
            hashed_password=get_password_hash(password),
            full_name="CLI Admin",
            role="admin",
            is_active=True,
        )
        db.add(admin_user)
        await db.commit()
        print(f"Success: Administrator account '{email}' created successfully.")


if __name__ == "__main__":
    if len(sys.argv) >= 3:
        email = sys.argv[1]
        password = sys.argv[2]
    else:
        print("Usage: python scripts/create_admin.py <email> <password>")
        print("Please enter credentials when prompted:")
        email = input("Admin Email: ").strip()
        password = input("Admin Password: ").strip()
        if not email or not password:
            print("Error: Email and password are required.")
            sys.exit(1)

    asyncio.run(create_admin(email, password))
