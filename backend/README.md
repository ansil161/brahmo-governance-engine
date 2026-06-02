# HealthScore Backend

A premium, production-ready FastAPI backend template implementing clean architecture, Repository Pattern, and seamless Supabase Auth integration.

## Project Structure

```text
backend/
│
├── app/
│   ├── api/
│   │   ├── v1/
│   │   │   ├── endpoints/          # Route handlers (auth, users, health)
│   │   │   └── router.py           # V1 endpoint registry
│   │
│   ├── core/                       # App settings, security, logging, constants, database setup
│   ├── models/                     # SQLAlchemy 2.0 declarative database models
│   ├── schemas/                    # Pydantic validation schemas
│   ├── repositories/               # Repository pattern CRUD database access layers
│   ├── services/                   # Business logic and external service integrations (Supabase)
│   ├── dependencies/               # FastAPI dependency injection functions
│   ├── middleware/                 # Rate-limiting, logger, CORS, request auth middleware
│   ├── utils/                      # Helper methods, pagination, standard responses
│   ├── workers/                    # Background scheduler and workers
│   └── main.py                     # Entry point for FastAPI application
│
├── alembic/                        # Database migration scripts
├── tests/                          # Automated pytest tests
├── scripts/                        # Database seeding & administrative scripts
├── Dockerfile                      # Application docker build file
└── docker-compose.yml              # Local docker-compose postgres and web stack
```

---

## Features

- **Asynchronous Stack**: Built on `FastAPI` and async `SQLAlchemy 2.0` with `asyncpg` / `aiosqlite`.
- **Supabase Integration**: Dual auth architecture. Accepts native credentials (local JWT sign) or external Supabase access tokens, automatically creating/syncing user records inside PostgreSQL.
- **Repository Pattern**: Separates database access queries from API routers and business services for scalability and unit testing.
- **Background Worker**: Built-in periodic task execution system running on an asyncio thread loop.
- **Clean API Logs & Rate-limiting**: Global request-latency tracker and rate-limit security middleware.
- **Swagger Docs Support**: Seamless native OpenAPI docs mounting for direct endpoint testing in the browser.

---

## Setup & Running Locally

### 1. Requirements

- Python 3.11+
- Virtualenv (`pip install virtualenv`)

### 2. Install Dependencies

In the `backend/` directory, create a virtual environment and install the packages:

```bash
python -m venv venv
# On Windows
venv\Scripts\activate
# On macOS/Linux
source venv/bin/activate

pip install -r requirements.txt
```

### 3. Environment Variables

Your `.env` file should contain the database credentials and Supabase configurations:

```env
# Database Configuration (Defaults to SQLite for local development)
DATABASE_URL=sqlite+aiosqlite:///./healthscore.db

# Supabase Auth Configuration
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-supabase-anon-key
SUPABASE_JWT_SECRET=your-jwt-secret
```

### 4. Run Seeding Script

Pre-populate the database with test accounts (admin and normal users):

```bash
python scripts/seed.py
```
- **Admin account**: `admin@healthscore.com` (password: `AdminPass123!`)
- **User account**: `user@healthscore.com` (password: `UserPass123!`)

To provision custom admin accounts:
```bash
python scripts/create_admin.py admin_email@example.com my_password
```

### 5. Running the Application

Start the local reloading uvicorn server:

```bash
uvicorn app.main:app --reload
```

Open your browser at **[http://localhost:8000/docs](http://localhost:8000/docs)** to view the Swagger UI.

---

## Running with Docker Compose

To spin up a fully local PostgreSQL database along with the FastAPI web app container, execute:

```bash
docker-compose up --build
```

---

## Running Automated Tests

Run the test suite (uses a fast, isolated in-memory SQLite database):

```bash
pytest -v
```
