# Hospital Agent Platform

The foundation provides the shared API, one worker process, PostgreSQL migrations, synthetic sessions, default-deny policy, request idempotency contracts, and an immutable agent registry. Durable execution and hospital workflows are implemented in later stages.

## Run with Docker Compose

1. Copy `.env.example` to `.env`. Set `SESSION_HASH_KEY` to a random value of at least 32 characters, set `DEMO_STAFF_PASSWORD` to a private demo password of at least 12 characters, and set `POSTGRES_PASSWORD` to a URL-safe password for Compose. If running commands on the host, put the same password in `DATABASE_URL`. Do not commit `.env`.
2. Run `docker compose up --build -d`. The API applies migrations and seeds the fixed synthetic tenant, demo staff account, and `hospital_frontdesk` workflow version before serving requests.
3. Check `http://localhost:8000/health/live` and `http://localhost:8000/health/ready`.
4. Create a synthetic patient session with `POST /session/patient`, or authenticate demo staff with `POST /session/staff` and the configured username/password. Use the returned token as `Authorization: Bearer <token>` for `GET /agents`.

Run a migration separately with `docker compose run --rm api alembic upgrade head`. Run checks with `python -m pytest` after installing the test dependencies.

The worker process currently checks database connectivity but does not claim jobs. Durable job processing starts in Stage 1.

## Local development

Use Python 3.12 or newer. Install with `python -m pip install -e '.[test]'`, set the variables from `.env.example`, run `alembic upgrade head`, then `python -m hospital_agent_platform.bootstrap.seed`. Start the API with `uvicorn hospital_agent_platform.api.main:app --reload` and the worker with `python -m hospital_agent_platform.worker.main`.

