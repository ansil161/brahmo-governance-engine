import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


@pytest.mark.asyncio
async def test_health_endpoint(client: AsyncClient) -> None:
    """Verify that the health check endpoint returns 200 and database health."""
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["database"] == "healthy"


@pytest.mark.asyncio
async def test_signup_endpoint(client: AsyncClient, db_session: AsyncSession) -> None:
    """Verify registration of a new user via the signup endpoint."""
    signup_data = {
        "email": "newuser@example.com",
        "password": "Password123!",
        "full_name": "New User Name",
    }
    response = await client.post("/api/v1/auth/signup", json=signup_data)
    assert response.status_code == 201
    
    data = response.json()
    assert data["email"] == "newuser@example.com"
    assert data["full_name"] == "New User Name"
    assert data["role"] == "user"
    assert data["is_active"] is True
    assert "id" in data


@pytest.mark.asyncio
async def test_login_endpoint(client: AsyncClient, test_user: User) -> None:
    """Verify user authentication and local JWT generation."""
    # Test successful login
    login_payload = {
        "username": "testuser@example.com",
        "password": "UserSecretPassword!",
    }
    response = await client.post("/api/v1/auth/login", data=login_payload)
    assert response.status_code == 200
    token_data = response.json()
    assert "access_token" in token_data
    assert token_data["token_type"] == "bearer"

    # Test failed login
    bad_login_payload = {
        "username": "testuser@example.com",
        "password": "WrongPassword!",
    }
    bad_response = await client.post("/api/v1/auth/login", data=bad_login_payload)
    assert bad_response.status_code == 400


@pytest.mark.asyncio
async def test_access_controls(
    client: AsyncClient, test_user: User, test_admin: User
) -> None:
    """Verify endpoint permissions: admin-only routes reject standard users."""
    # 1. Login as standard user to get token
    user_payload = {
        "username": "testuser@example.com",
        "password": "UserSecretPassword!",
    }
    user_login = await client.post("/api/v1/auth/login", data=user_payload)
    user_token = user_login.json()["access_token"]
    user_headers = {"Authorization": f"Bearer {user_token}"}

    # 2. Login as admin to get token
    admin_payload = {
        "username": "testadmin@example.com",
        "password": "AdminSecretPassword!",
    }
    admin_login = await client.post("/api/v1/auth/login", data=admin_payload)
    admin_token = admin_login.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # 3. Test GET /users with standard user (should be 403 Forbidden)
    response_user = await client.get("/api/v1/users", headers=user_headers)
    assert response_user.status_code == 403

    # 4. Test GET /users with admin (should be 200 OK)
    response_admin = await client.get("/api/v1/users", headers=admin_headers)
    assert response_admin.status_code == 200
    data = response_admin.json()
    assert "items" in data
    assert len(data["items"]) >= 2  # Includes test_user and test_admin
