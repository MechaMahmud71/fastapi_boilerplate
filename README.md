# FastAPI Boilerplate

A modular, async FastAPI starter with a NestJS-style layered architecture:
dependency-injected controllers, services and repositories, a uniform response
envelope, centralised error handling, JWT auth, SQLAlchemy 2.0 and Alembic
migrations.

---

## Table of contents

- [Stack](#stack)
- [Architecture](#architecture)
  - [Layers](#layers)
  - [Request lifecycle](#request-lifecycle)
  - [Dependency injection](#dependency-injection)
  - [Imports](#imports)
  - [Response envelope](#response-envelope)
  - [Error handling](#error-handling)
  - [Authentication](#authentication)
  - [Building decorators (NestJS-style)](#building-decorators-nestjs-style)
  - [Project layout](#project-layout)
- [Getting started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [1. Clone and create a virtualenv](#1-clone-and-create-a-virtualenv)
  - [2. Configure environment](#2-configure-environment)
  - [3. Start PostgreSQL](#3-start-postgresql)
  - [4. Run migrations](#4-run-migrations)
  - [5. Run the app](#5-run-the-app)
- [Database migrations](#database-migrations)
- [API reference](#api-reference)
- [Deployment](#deployment)
  - [Production checklist](#production-checklist)
  - [Option A — Docker Compose](#option-a--docker-compose)
  - [Option B — systemd on a VM](#option-b--systemd-on-a-vm)
  - [Reverse proxy (nginx)](#reverse-proxy-nginx)
  - [Production environment variables](#production-environment-variables)
- [Testing](#testing)
  - [Which kind of test to write](#which-kind-of-test-to-write)
  - [Writing a unit test](#writing-a-unit-test)
  - [Writing an e2e test](#writing-an-e2e-test)
  - [Recording a known bug](#recording-a-known-bug)
  - [Conventions](#conventions)
- [Adding a new module](#adding-a-new-module)
- [Known issues](#known-issues)

---

## Stack

| Concern            | Choice                                        |
| ------------------ | --------------------------------------------- |
| Web framework      | FastAPI                                       |
| ASGI server        | Uvicorn                                       |
| ORM                | SQLAlchemy 2.0 (async, typed `Mapped` models) |
| Database driver    | asyncpg                                       |
| Database           | PostgreSQL 17 (via Docker Compose)            |
| Migrations         | Alembic (async template)                      |
| Validation         | Pydantic v2                                   |
| DI container       | `dependency-injector`                         |
| Auth               | PyJWT + passlib/bcrypt                        |
| Config             | python-dotenv                                 |

**Python 3.10+ is required.** The codebase uses `X | None` union syntax, which
is a runtime error on 3.9.

---

## Architecture

### Layers

Each feature lives in `src/modules/<feature>/` and is split into four layers. Data
flows strictly downward; each layer only knows about the one directly below it.

```
HTTP request
     │
     ▼
┌─────────────────┐
│   Controller    │  routing, HTTP concerns, request/response DTOs
│  *_controller   │  owns an APIRouter, no business logic
└────────┬────────┘
         ▼
┌─────────────────┐
│    Service      │  business rules, orchestration, hashing, tokens
│   *_service     │  no SQL, no HTTP
└────────┬────────┘
         ▼
┌─────────────────┐
│   Repository    │  all database access, owns the session lifecycle
│  *_repository   │  returns ORM models
└────────┬────────┘
         ▼
┌─────────────────┐
│     Model       │  SQLAlchemy 2.0 declarative table
│    *_model      │
└─────────────────┘
```

**DTOs** (`src/modules/<feature>/dtos/`) are Pydantic models describing request
bodies. They are the boundary contract; ORM models never come in from the
outside.

Why the split matters: the repository is the only layer that touches
SQLAlchemy, so swapping the persistence layer or unit-testing a service with a
fake repository requires no changes elsewhere.

### Request lifecycle

A request passes through several layers of middleware before and after your
handler runs:

```
   request
      │
      ▼
┌──────────────────────────┐
│  ServerErrorMiddleware   │  catches anything unhandled → GenericErrorHandler
│ ┌──────────────────────┐ │
│ │ ResponseInterceptor  │ │  wraps the outgoing body in the envelope
│ │ ┌──────────────────┐ │ │
│ │ │ExceptionMiddlware│ │ │  HTTPException / RequestValidationError handlers
│ │ │ ┌──────────────┐ │ │ │
│ │ │ │    Router    │ │ │ │  path match → @Protected → controller handler
│ │ │ └──────────────┘ │ │ │
│ │ └──────────────────┘ │ │
│ └──────────────────────┘ │
└──────────────────────────┘
      │
      ▼
   response
```

The ordering matters: because `ResponseInterceptor` sits *outside* the
exception middleware, handled errors (`HttpError`, validation failures) are
already serialised by the time the interceptor sees them, so it detects the
envelope and passes them through untouched instead of double-wrapping.

### Dependency injection

Wiring lives in [`src/utils/container.py`](src/utils/container.py). Providers are
declared once and composed; nothing constructs its own dependencies.

```python
db_factory      = providers.Object(AsyncSessionLocal)
user_repository = providers.Factory(UserRepository, db_factory=db_factory)
user_service    = providers.Factory(UserService, user_repo=user_repository)
user_controller = providers.Factory(UserController, user_service=user_service)
```

[`router.py`](router.py) resolves the controllers from the container and mounts
their routers:

```python
user_controller = container.user_controller()
api_router.include_router(user_controller.router)
```

Controllers are **classes**, not modules of functions. Each builds its own
`APIRouter` in `__init__` and registers routes in a private `__add_routes`
method, so the injected service is available to every handler via `self`.

The session factory is injected as a *factory*, not a session. Each repository
method opens and closes its own `async with self.db_factory() as db:` scope,
so a session never outlives a single call.

### Imports

The project uses **implicit namespace packages** — there are no `__init__.py`
files anywhere. Every import names the module that actually defines the symbol:

```python
from src.modules.user.user_service import UserService
from src.modules.user.dtos.create_dto import CreateUserDTO
from src.modules.common.decorators.protected_decorator import Protected
from src.utils.expection import HttpError
```

Package-level re-exports (`from src.modules.user import UserService`) are
deliberately absent. They read more nicely, but they made importing any symbol
from a package execute that package's whole `__init__.py` — which pulled the
controller, and therefore the decorators and `utils`, into every service. That
produced a genuine import cycle: `src.utils` → `container` → controllers →
services → `src.utils`, which is why nothing could be imported except through
`main`.

Two consequences worth knowing:

* **Every module imports standalone**, so a test can import one service without
  building the whole app.
* **Packaging needs `find_namespace_packages()`**, not `find_packages()` — the
  latter skips directories without `__init__.py` and would ship nothing.

### Response envelope

**Every** JSON response from the API uses one of two envelopes, with a stable
key order.

**Success:**

```json
{
  "success": true,
  "data": {},
  "message": null
}
```

**Error** — adds an `errors` array:

```json
{
  "success": false,
  "data": null,
  "errors": ["password: Field required"],
  "message": "password: Field required"
}
```

| Field     | Type              | Meaning                                                      |
| --------- | ----------------- | ------------------------------------------------------------ |
| `success` | `boolean`         | Derived from the HTTP status code (`< 400`)                   |
| `data`    | `object \| null`  | The handler's return value on success; `null` on errors       |
| `errors`  | `string[]`        | Errors only. One entry per invalid field                      |
| `message` | `string \| null`  | `null` on success; on errors, the entries joined with `"; "`  |

`errors` is always present on a failure and always a list of strings. For
errors that are not field-level (a 404, a raised `HttpError`, an unhandled
exception) it holds a single element equal to `message`, so a client can render
`errors` uniformly without special-casing.

This is applied centrally by
[`ResponseInterceptor`](src/modules/common/interceptors/response_interceptor.py),
so **controllers just return their payload** — no wrapping by hand:

```python
@self.router.get("/{user_id}")
async def get_user(user_id: int):
    return await self.user_service.get_user(user_id)   # → {"success": true, "data": {...}, "message": null}
```

Both shapes are defined in one place, [`src/utils/response.py`](src/utils/response.py)
(`envelope` and `error_envelope`), and shared with the error handlers so the
two can never drift apart.

The interceptor handles three cases:

1. **Already an envelope** (produced by an error handler) — passed through as-is.
2. **A FastAPI error body** (`{"detail": ...}` on a 4xx/5xx) — `detail` is
   lifted into `message` and `errors`, so framework 404/405/401 responses match
   your own.
3. **Anything else** — placed in `data` verbatim.

It deliberately does *not* inspect payload keys on success. An earlier version
promoted any `message` field and unwrapped any `data` field it found, which
silently corrupted records that happened to use those column names.

Non-JSON responses and the `/docs`, `/redoc`, `/openapi` routes bypass the
interceptor entirely.

### Error handling

Raise [`HttpError`](src/utils/expection.py) anywhere — services included — and the
right response comes out the other end:

```python
from src.utils import HttpError

if not user:
    raise HttpError("User not found", 404)
```

```json
{
  "success": false,
  "data": null,
  "errors": ["User not found"],
  "message": "User not found"
}
```

All three build their body with `error_envelope`. They are registered in
[`main.py`](main.py) and defined in
[`error_handler_middleware.py`](src/modules/common/middlewares/error_handler_middleware.py):

| Handler                      | Catches                   | Status                |
| ---------------------------- | ------------------------- | --------------------- |
| `HttpErrorHandler`           | `HTTPException` / `HttpError` | the exception's own |
| `ValidationExceptionHandler` | `RequestValidationError`  | `422`                 |
| `GenericErrorHandler`        | any unhandled `Exception` | `500`                 |

`GenericErrorHandler` logs the traceback server-side and returns a fixed
`"Internal Server Error"` message — exception text never reaches the client.
`HttpErrorHandler` is registered on Starlette's base `HTTPException`, so
router-raised `404`/`405` responses use the same envelope as your own errors.

Validation failures list one entry per invalid field, and join them into
`message`:

```json
{
  "success": false,
  "data": null,
  "errors": ["username: Field required", "password: Field required"],
  "message": "username: Field required; password: Field required"
}
```

### Authentication

Registration hashes the password with bcrypt and returns a signed JWT. Both
auth routes return the payload bare — the envelope is added by the interceptor:

```json
{
  "success": true,
  "data": {
    "user": { "id": 1, "username": "alice" },
    "accessToken": "eyJhbGciOiJIUzI1NiIs..."
  },
  "message": null
}
```

Protect a route with the
[`@Protected`](src/modules/common/decorators/protected_decorator.py) decorator — it
acts as an auth guard. It verifies the `Authorization: Bearer <token>` header,
rejects a missing/invalid/expired token with `401`, and attaches the decoded
payload to `request.state.user`, which
[`get_current_user`](src/helpers/get_current_user.py) reads back:

```python
@self.router.get("/me")
@Protected
async def get_me(request: Request):
    return await get_current_user(request)
```

The decorator appends its own `HTTPBearer` dependency to the handler signature,
so the route is **documented as secured in OpenAPI automatically** — Swagger
renders the padlock and the Authorize button with no extra `Security(...)`
declaration. It works on handlers with any mix of path, query and body
parameters, and `request` is optional:

```python
@self.router.delete("/{user_id}")
@Protected
async def delete_user(user_id: int, request: Request):
    return await self.user_service.delete_user(user_id)
```

### Building decorators (NestJS-style)

[`src/utils/decorators.py`](src/utils/decorators.py) provides three factories that
mirror Nest's decorator toolkit, so guards and injectors are declarative rather
than hand-rolled:

| Factory                    | Nest equivalent         | Purpose                                  |
| -------------------------- | ----------------------- | ---------------------------------------- |
| `create_guard(fn, ...)`    | `@UseGuards` / `CanActivate` | Run a check before the handler      |
| `set_metadata(key, value)` | `@SetMetadata`          | Attach metadata a guard can read          |
| `create_param_decorator(fn)` | `createParamDecorator` | Inject a computed value as a parameter   |

A guard receives an `ExecutionContext` (`request`, `credentials`, `metadata`,
and values produced by earlier guards). Return `False` to reject, raise
`HttpError` for a custom response, or return a value to publish it under the
guard's `provides` name.

```python
from src.utils.decorators import ExecutionContext, create_guard, create_param_decorator

def api_key_guard(ctx: ExecutionContext) -> bool:
    return ctx.request.headers.get("X-API-Key") == expected_key

ApiKey = create_guard(api_key_guard, message="Bad API key", status_code=403)

@router.get("/keyed")
@ApiKey
async def keyed():
    return {"ok": True}
```

The auth decorators are built with these, one concern per file:

```python
# src/modules/common/decorators/protected_decorator.py  — authentication
Protected   = create_guard(jwt_guard, security=bearer_scheme, provides="user")

# src/modules/common/decorators/role_decorator.py       — authorisation
RoleGuard   = create_guard(roles_guard, message="Insufficient permissions", status_code=403)
Roles       = lambda *roles: set_metadata("roles", list(roles))

# src/modules/common/decorators/user_decorator.py       — parameter injection
CurrentUser = create_param_decorator(lambda ctx: ctx.get("user"))
```

Guards **stack**, and metadata flows into them — the `@Roles` + `RoleGuard`
pairing is exactly Nest's:

```python
@self.router.get("/admin")
@Protected                       # 401 if the token is missing/invalid
@RoleGuard                       # 403 unless the role matches
@Roles("admin")                  # metadata read by RoleGuard
async def admin_only(user: dict = CurrentUser):
    return {"secret": "only admins"}
```

Two implementation details worth knowing:

* Guards run as **FastAPI dependencies**, inserted at the front of the handler
  signature, so they resolve *before* any `create_param_decorator` value the
  handler injects. That ordering is what lets `CurrentUser` see what `Protected`
  produced.
* Passing `security=` (e.g. `HTTPBearer`) also declares the scheme to OpenAPI,
  so protected routes show the padlock in Swagger with no extra
  `Security(...)` declaration.

### Project layout

```
.
├── main.py                      # app factory, CORS, docs gating, handler registration
├── Dockerfile                   # multi-stage production image (non-root)
├── docker-compose.prod.yml      # production stack: api + postgres
├── .env.production.example      # production configuration template
├── scripts/entrypoint.sh        # waits for the DB, migrates, execs the server
├── deploy/fastapi-app.service   # systemd unit for VM deployments
├── router.py                    # resolves controllers from the DI container, mounts routers
├── alembic.ini                  # Alembic config (DB URL is injected at runtime)
├── docker-compose.yml           # PostgreSQL + pgAdmin
│
├── src/                         # application package
│   ├── modules/
│   │   ├── auth/                # login / register
│   │   │   ├── auth_controller.py
│   │   │   ├── auth_service.py          # JWT issuing, credential checks
│   │   │   └── dtos/
│   │   ├── user/                # user CRUD
│   │   │   ├── user_controller.py
│   │   │   ├── user_service.py          # hashing, uniqueness, 404s
│   │   │   ├── user_repository.py
│   │   │   ├── user_model.py
│   │   │   └── dtos/                    # Create / Update / UserPublic
│   │   ├── health/              # liveness + readiness probes
│   │   ├── todo/                # todo CRUD, owned by a user
│   │   │   ├── todo_controller.py
│   │   │   ├── todo_service.py          # ownership rules
│   │   │   ├── todo_repository.py
│   │   │   ├── todo_model.py            # FK to users, ON DELETE CASCADE
│   │   │   └── dtos/                    # Create / Update / TodoPublic
│   │   └── common/              # cross-cutting concerns
│   │       ├── interceptors/            # ResponseInterceptor
│   │       ├── middlewares/             # error handlers
│   │       ├── decorators/
│   │       │   ├── protected_decorator.py   # @Protected (authn)
│   │       │   ├── role_decorator.py        # @RoleGuard, @Roles (authz)
│   │       │   └── user_decorator.py        # CurrentUser (param injection)
│   │       └── services/                # ConfigService (.env access)
│   │
│   ├── utils/
│   │   ├── container.py         # dependency-injector wiring
│   │   ├── db_connection.py     # async engine, session factory, declarative Base
│   │   ├── response.py          # the response envelope
│   │   ├── decorators.py        # guard / metadata / param-decorator factories
│   │   ├── security.py          # password hashing helpers
│   │   └── expection.py         # HttpError
│   │
│   └── helpers/
│       └── get_current_user.py
│
├── migrations/                  # Alembic migration environment
│   ├── env.py                   # reads DATABASE_URL, points at Base.metadata
│   └── versions/                # migration scripts
│
└── tests/
    ├── conftest.py              # JWT fixtures + the async-test runner
    ├── asgi_client.py           # dependency-free ASGI client
    ├── unit/                    # no database
    └── e2e/                     # real app + real database
```

---

## Getting started

### Prerequisites

- **Python 3.10 or newer** (3.9 will fail at import time)
- **Docker** and Docker Compose — for PostgreSQL
- `git`

### 1. Clone and create a virtualenv

```bash
git clone <repo-url>
cd fastapi_boilerplate

python3 -m venv venv
source venv/bin/activate           # Windows: venv\Scripts\activate

pip install --upgrade pip
pip install -r requirements.txt
```

### 2. Configure environment

Copy the example file and adjust as needed:

```bash
cp .env.example .env
```

| Variable          | Description                                   | Example                                                     |
| ----------------- | --------------------------------------------- | ----------------------------------------------------------- |
| `DATABASE_URL`    | Async PostgreSQL DSN                          | `postgresql+asyncpg://faruk:faruk@localhost:5434/todo`      |
| `JWT_SECRET`      | Signing key for access tokens — change this   | `dev-secret-change-me`                                       |
| `JWT_ALGORITHM`   | JWT algorithm                                 | `HS256`                                                      |
| `JWT_EXPIRE_TIME` | Access token lifetime, in minutes             | `60`                                                         |

`.env` is gitignored and is read at import time — the app will not start
without `DATABASE_URL`. A `postgresql://` URL is rewritten to
`postgresql+asyncpg://` automatically.

### 3. Start PostgreSQL

```bash
docker compose up -d postgres
```

Postgres is published on **host port 5434** (container port 5432) to avoid
colliding with a local Postgres or another project on 5432. Change the mapping
in `docker-compose.yml` and `DATABASE_URL` together if you prefer another port.

Compose also defines a **pgAdmin** service on <http://localhost:5050>
(`admin@admin.com` / `root`). Start it with `docker compose up -d` if you want
it — inside pgAdmin, connect to host `postgres`, port `5432`.

Check it is accepting connections:

```bash
docker exec container-postgres pg_isready -U faruk -d todo
```

### 4. Run migrations

The database starts empty. Create the schema:

```bash
alembic upgrade head
```

Verify:

```bash
docker exec container-postgres psql -U faruk -d todo -c '\dt'
```

### 5. Run the app

```bash
source venv/bin/activate          # skip if your venv is already active
uvicorn main:app --reload
```

The server starts on <http://127.0.0.1:8000>. `--reload` restarts it whenever a
file changes — use it in development only.

**Common variations:**

```bash
# pick a port (handy when 8000 is taken)
uvicorn main:app --reload --port 8001

# reachable from other devices on your network (phone, another laptop, Docker)
uvicorn main:app --host 0.0.0.0 --port 8000

# production: several worker processes, no reloader
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4

# quieter, or noisier
uvicorn main:app --reload --log-level warning
uvicorn main:app --reload --log-level debug

# without activating the venv
./venv/bin/uvicorn main:app --reload

# if the `uvicorn` command is not on your PATH
python -m uvicorn main:app --reload
```

**Full start from cold** — every step needed after a reboot:

```bash
docker compose up -d postgres     # 1. database
source venv/bin/activate          # 2. environment
alembic upgrade head              # 3. schema (no-op if already current)
uvicorn main:app --reload         # 4. server
```

**Stopping:** `Ctrl+C` in the terminal running uvicorn. To stop a server you
started in the background, and the database:

```bash
pkill -f "uvicorn main:app"
docker compose down               # add -v to also delete the database volume
```

| URL                                              | What                    |
| ------------------------------------------------ | ----------------------- |
| <http://127.0.0.1:8000>                          | API root                |
| <http://127.0.0.1:8000/docs>                     | Swagger UI              |
| <http://127.0.0.1:8000/redoc>                    | ReDoc                   |
| <http://127.0.0.1:8000/openapi.json>             | OpenAPI schema          |

Smoke test — register a user, then call a protected route with the token it
returns:

```bash
curl -X POST http://127.0.0.1:8000/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"username":"alice","password":"secret123"}'

TOKEN="<accessToken from the response>"

curl http://127.0.0.1:8000/users/me -H "Authorization: Bearer $TOKEN"
```

**Troubleshooting:**

| Symptom | Cause |
| --- | --- |
| `ERROR: [Errno 48] Address already in use` | Another process holds the port — use `--port 8001`, or `pkill -f "uvicorn main:app"` |
| `TypeError: unsupported operand type(s) for \|` | Python 3.9 — this project needs **3.10+** |
| `ConnectionRefusedError` on the first request | PostgreSQL is not running: `docker compose up -d postgres` |
| `relation "users" does not exist` | Migrations not applied: `alembic upgrade head` |
| `AttributeError: 'NoneType' ... DATABASE_URL` | No `.env` file: `cp .env.example .env` |

------------------------------------------------ | ----------------------- |
| <http://127.0.0.1:8000>                          | API root                |
| <http://127.0.0.1:8000/docs>                     | Swagger UI              |
| <http://127.0.0.1:8000/redoc>                    | ReDoc                   |
| <http://127.0.0.1:8000/openapi.json>             | OpenAPI schema          |

Smoke test:

```bash
curl -X POST http://127.0.0.1:8000/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"username":"alice","password":"secret123"}'
```

---

## Database migrations

Schema is owned by Alembic. `main.py` does **not** call
`Base.metadata.create_all` — that would race with migrations and let the two
drift apart.

[`migrations/env.py`](migrations/env.py) is wired to the app: it reads
`DATABASE_URL` from `.env` at runtime (so `sqlalchemy.url` in `alembic.ini`
stays commented out) and points `target_metadata` at the app's `Base`.

**Every model must be imported in `migrations/env.py`** or autogenerate will
not see it — and will happily generate a migration that drops its table:

```python
from src.modules.user.user_model import User  # noqa: F401
```

### Common commands

```bash
alembic upgrade head                        # apply all pending migrations
alembic revision --autogenerate -m "add todos table"
alembic downgrade -1                        # roll back one migration
alembic current                             # which revision is applied
alembic history --verbose                   # full migration log
```

### Workflow for a schema change

1. Edit the model (e.g. add a column to `user_model.py`).
2. Import the model in `migrations/env.py` if it is new.
3. `alembic revision --autogenerate -m "describe the change"`
4. **Read the generated file.** Autogenerate is a first draft, not an oracle.
5. `alembic upgrade head`

### Autogenerate caveats

- **Column type/length changes are not detected** by default, so changing
  `String(50)` → `String(100)` produces an empty migration. Either add the
  `op.alter_column(..., type_=...)` call by hand, or set
  `compare_type=True` in `env.py`'s `context.configure(...)`.
- Table and column **renames** are detected as a drop plus an add, which loses
  data. Rewrite these as `op.alter_column(..., new_column_name=...)`.
- Server defaults are not compared unless `compare_server_default=True`.

---

## API reference

All responses use the [envelope](#response-envelope) described above.

### Auth — `/auth`

| Method | Path             | Body                       | Description                        |
| ------ | ---------------- | -------------------------- | ---------------------------------- |
| `POST` | `/auth/register` | `{ username, password }`   | Create a user, return a JWT        |
| `POST` | `/auth/login`    | `{ username, password }`   | Verify credentials, return a JWT   |

Both return `data: { user, accessToken }`.

### Users — `/users`

| Method   | Path              | Auth | Success | Description                       |
| -------- | ----------------- | ---- | ------- | --------------------------------- |
| `POST`   | `/users/`         | JWT  | `201`   | Create a user (password hashed)   |
| `GET`    | `/users/`         | JWT  | `200`   | List all users                    |
| `GET`    | `/users/me`       | JWT  | `200`   | Current user from token           |
| `GET`    | `/users/{id}`     | JWT  | `200`   | Fetch one user (`404` if missing) |
| `PUT`    | `/users/{id}`     | JWT  | `200`   | Partial update (`404` if missing) |
| `DELETE` | `/users/{id}`     | JWT  | `200`   | Delete a user (`404` if missing)  |

User responses are serialised through `UserPublicDTO` (`id`, `username`), so a
password hash is never returned. A duplicate username is a `409`.

### Todos — `/todos`

Every todo belongs to exactly one user (**one-to-many**), and every route is
scoped to the caller's own todos.

| Method   | Path            | Auth | Success | Description                        |
| -------- | --------------- | ---- | ------- | ---------------------------------- |
| `POST`   | `/todos/`       | JWT  | `201`   | Create a todo for the current user |
| `GET`    | `/todos/`       | JWT  | `200`   | List the caller's todos (paginated)|
| `GET`    | `/todos/{id}`   | JWT  | `200`   | Fetch one (`404` if not yours)     |
| `PUT`    | `/todos/{id}`   | JWT  | `200`   | Partial update (`404` if not yours)|
| `DELETE` | `/todos/{id}`   | JWT  | `200`   | Delete (`404` if not yours)        |

`GET /todos/` accepts `completed` (`true`/`false`), `limit` (1–100, default 50)
and `offset`, and returns a paginated envelope where `total` is the unpaginated
count:

```json
{
  "success": true,
  "data": {
    "items": [
      {"id": 1, "title": "buy milk", "description": "2L", "completed": false, "user_id": 7}
    ],
    "total": 1,
    "limit": 50,
    "offset": 0
  },
  "message": null
}
```

**A todo belonging to another user returns `404`, not `403`.** A `403` would
confirm the id exists; `404` reveals nothing about other users' data.

**Deleting a user deletes their todos.** The foreign key is
`ON DELETE CASCADE`, and the relationship uses `passive_deletes=True` so the
database performs the cascade rather than SQLAlchemy loading each row.

Example of an authenticated call:

```bash
curl http://127.0.0.1:8000/users/me \
  -H "Authorization: Bearer <accessToken>"
```

---

## Deployment

Two supported paths: **Docker Compose** (recommended) or **systemd on a VM**.
Both apply migrations before serving traffic.

### Production checklist

Before the first deploy:

- [ ] Generate a real `JWT_SECRET` (32+ bytes) — the dev placeholder is unsafe
- [ ] Set `APP_ENV=production` (disables `/docs`, `/redoc`, `/openapi.json`)
- [ ] Set `CORS_ORIGINS` to your exact frontend origins (empty = CORS off)
- [ ] Use a strong `POSTGRES_PASSWORD`; never ship `faruk/faruk`
- [ ] Put TLS in front (nginx, Caddy, or a load balancer) — uvicorn should not face the internet
- [ ] Point your load balancer at `GET /health/ready`
- [ ] Confirm `.env.production` is not committed (`.env*` is gitignored)

### Option A — Docker Compose

```bash
# 1. configuration
cp .env.production.example .env.production
python -c "import secrets; print(secrets.token_urlsafe(32))"   # paste as JWT_SECRET
$EDITOR .env.production

# 2. build
docker compose -f docker-compose.prod.yml --env-file .env.production build

# 3. start (database first, then the API once it is healthy)
docker compose -f docker-compose.prod.yml --env-file .env.production up -d

# 4. verify
docker compose -f docker-compose.prod.yml ps
curl -fsS http://127.0.0.1:8000/health
curl -fsS http://127.0.0.1:8000/health/ready
```

Migrations run automatically in the container entrypoint before the server
starts. Set `RUN_MIGRATIONS=false` to skip that — for example when several
replicas start at once and only one should migrate.

**Operating it:**

```bash
docker compose -f docker-compose.prod.yml logs -f api      # follow logs
docker compose -f docker-compose.prod.yml restart api      # restart
docker compose -f docker-compose.prod.yml down             # stop (keeps data)
docker compose -f docker-compose.prod.yml down -v          # stop AND DELETE the database volume
```

**Redeploying a new version:**

```bash
git pull
docker compose -f docker-compose.prod.yml --env-file .env.production build
docker compose -f docker-compose.prod.yml --env-file .env.production up -d
```

**Running a migration by hand** (or any one-off command):

```bash
docker compose -f docker-compose.prod.yml exec api alembic upgrade head
docker compose -f docker-compose.prod.yml exec api alembic current
docker compose -f docker-compose.prod.yml exec postgres psql -U app -d app
```

**Database backup and restore:**

```bash
docker compose -f docker-compose.prod.yml exec -T postgres \
  pg_dump -U app app > backup-$(date +%F).sql

cat backup-2026-09-02.sql | docker compose -f docker-compose.prod.yml exec -T postgres \
  psql -U app app
```

### Option B — systemd on a VM

```bash
# 1. code and dependencies
sudo useradd --system --create-home --home-dir /srv/app appuser
sudo -u appuser git clone <repo> /srv/app
cd /srv/app
sudo -u appuser python3.12 -m venv venv
sudo -u appuser ./venv/bin/pip install -r requirements.txt

# 2. configuration
sudo -u appuser cp .env.production.example .env.production
sudo -u appuser $EDITOR .env.production            # set DATABASE_URL and JWT_SECRET
sudo chmod 600 /srv/app/.env.production

# 3. install the service
sudo cp deploy/fastapi-app.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now fastapi-app

# 4. verify
sudo systemctl status fastapi-app
curl -fsS http://127.0.0.1:8000/health/ready
```

The unit runs `alembic upgrade head` as `ExecStartPre`, so migrations are
applied on every start and restart.

**Operating it:**

```bash
sudo journalctl -u fastapi-app -f          # follow logs
sudo systemctl restart fastapi-app         # restart
sudo systemctl stop fastapi-app            # stop
```

**Redeploying:**

```bash
cd /srv/app
sudo -u appuser git pull
sudo -u appuser ./venv/bin/pip install -r requirements.txt
sudo systemctl restart fastapi-app         # migrations run via ExecStartPre
```

### Reverse proxy (nginx)

Uvicorn does not terminate TLS. Put nginx in front:

```nginx
server {
    listen 443 ssl http2;
    server_name api.example.com;

    ssl_certificate     /etc/letsencrypt/live/api.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.example.com/privkey.pem;

    location / {
        proxy_pass         http://127.0.0.1:8000;
        proxy_set_header   Host              $host;
        proxy_set_header   X-Real-IP         $remote_addr;
        proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
    }
}
```

Add `--proxy-headers --forwarded-allow-ips='*'` to the uvicorn command so the
app sees the real client IP and scheme.

### Health endpoints

| Endpoint        | Checks                    | Use for                                   |
| --------------- | ------------------------- | ----------------------------------------- |
| `/health`       | process is up             | container liveness — restart if it fails  |
| `/health/ready` | database is reachable     | load balancer readiness — `503` pulls the instance out of rotation |

Neither requires a token.

### Production environment variables

| Variable | Default | Notes |
| --- | --- | --- |
| `APP_ENV` | `development` | `production` disables docs and defaults CORS to closed |
| `DATABASE_URL` | — | required; `postgresql+asyncpg://…` |
| `JWT_SECRET` | — | required; 32+ bytes |
| `JWT_ALGORITHM` | `HS256` | |
| `JWT_EXPIRE_TIME` | `60` | access-token lifetime, minutes |
| `CORS_ORIGINS` | `*` in dev, empty in prod | comma-separated exact origins |
| `CORS_ALLOW_CREDENTIALS` | `true` | |
| `ENABLE_DOCS` | on in dev, off in prod | forces `/docs` on or off |
| `LOG_LEVEL` | `INFO` | |
| `RUN_MIGRATIONS` | `true` | container entrypoint only |
| `APP_NAME` / `APP_VERSION` | boilerplate defaults | shown in OpenAPI |

### Scaling notes

* **Workers:** `(2 × CPU cores) + 1` is the usual starting point. Each worker
  holds its **own** database connection pool, so `workers × pool_size` must stay
  under Postgres' `max_connections` (default 100).
* **Multiple replicas:** set `RUN_MIGRATIONS=false` on all but one, or run
  `alembic upgrade head` as a separate deploy step, so replicas do not race.
* **Graceful shutdown:** the entrypoint `exec`s uvicorn so it becomes PID 1 and
  receives `SIGTERM` directly; in-flight requests finish before exit.

## Testing

```bash
pip install -r requirements-dev.txt

pytest                    # everything
pytest tests/unit         # fast, no database
pytest tests/e2e          # full stack, needs PostgreSQL running
pytest -k auth            # anything matching "auth"
pytest tests/unit/user -v # one module, verbose
pytest -x                 # stop at the first failure
```

### Layout

```
tests/
├── conftest.py             # JWT fixtures + the async-test runner
├── asgi_client.py          # dependency-free ASGI client
├── unit/                   # no database, no network
│   ├── common/
│   │   ├── test_decorators.py           # guards, metadata, param decorators
│   │   ├── test_response_interceptor.py # the success/error envelopes
│   │   └── test_error_handlers.py       # the three exception handlers
│   ├── auth/test_auth_service.py        # hashing, tokens, rejections
│   └── user/test_user_service.py        # delegation to the repository
└── e2e/                    # real app + real database
    ├── conftest.py         # session loop, DB reset between tests
    ├── test_auth_e2e.py    # register / login flows
    └── test_users_e2e.py   # CRUD + the /users/me guard
```

Mirror the `src/modules/` tree: a new `src/modules/todo/` gets `tests/unit/todo/` and a
`tests/e2e/test_todo_e2e.py`.

### Which kind of test to write

| | Unit | E2E |
| --- | --- | --- |
| Lives in | `tests/unit/<module>/` | `tests/e2e/` |
| Database | none — the layer below is faked | real PostgreSQL |
| Asserts | business rules, in isolation | HTTP status, envelope, persistence |
| Speed | milliseconds | ~100ms per test |
| Use for | services, guards, interceptors, DTO rules | routes, auth flows, wiring |

Rule of thumb: **every branch of a service belongs in a unit test; every route
gets at least one e2e test** for its success path and its main failure.

---

### Writing a unit test

Unit tests replace the layer below with a fake, so nothing touches the network
or the database. Services take their dependency through `__init__`, which makes
this straightforward — no patching or mocking library needed.

**1. Write a fake for the layer below.** Implement only the methods your subject
calls, and record the calls you want to assert on:

```python
class FakeTodoRepository:
    def __init__(self, todos=None):
        self.todos = {t.id: t for t in (todos or [])}
        self.calls = []

    async def get_todo_by_id(self, todo_id: int):
        self.calls.append(("get_todo_by_id", todo_id))
        return self.todos.get(todo_id)

    async def create_todo(self, dto):
        self.calls.append(("create_todo", dto))
        todo = Todo(id=1, title=dto.title)
        self.todos[todo.id] = todo
        return todo
```

**2. Wire it up with fixtures:**

```python
@pytest.fixture
def repo():
    return FakeTodoRepository([Todo(id=1, title="write tests")])

@pytest.fixture
def service(repo):
    return TodoService(repo)
```

**3. Write `async def` tests directly** — no `@pytest.mark.asyncio` needed, the
hook in `tests/conftest.py` runs them:

```python
async def test_get_todo_returns_the_match(service):
    assert (await service.get_todo(1)).title == "write tests"

async def test_get_todo_returns_none_when_missing(service):
    assert await service.get_todo(999) is None

async def test_create_todo_delegates_to_the_repository(service, repo):
    dto = CreateTodoDTO(title="new")
    await service.create_todo(dto)
    assert repo.calls[-1] == ("create_todo", dto)
```

**Asserting a raised `HttpError`** — check the status code and message, not just
the type:

```python
async def test_login_rejects_unknown_user():
    service = AuthService(FakeUserService())

    with pytest.raises(HttpError) as exc:
        await service.login(LoginDTO(username="ghost", password="x"))

    assert exc.value.status_code == 404
    assert exc.value.detail == "User not found"
```

**Testing middleware or a decorator** rather than a service? Build a throwaway
`FastAPI` app in a fixture with routes that exercise the behaviour, and drive it
with `ASGIClient` — see
[`test_response_interceptor.py`](tests/unit/common/test_response_interceptor.py):

```python
@pytest.fixture
def client():
    app = FastAPI()
    app.add_middleware(ResponseInterceptor)
    app.add_exception_handler(HTTPException, HttpErrorHandler)

    @app.get("/none")
    async def as_none():
        return None

    return ASGIClient(app)


def test_null_payload_does_not_crash(client):
    assert client.get("/none").json()["data"] is None
```

Note these are plain `def` tests: `ASGIClient` is synchronous.

---

### Writing an e2e test

E2E tests exercise the real `main.app` — real router, real DI container, real
interceptor and error handlers, real PostgreSQL.

> **The e2e suite runs `DELETE FROM users` before and after every test**, against
> whatever `DATABASE_URL` your `.env` points at. Point it at a throwaway
> database. The whole suite is skipped automatically if PostgreSQL is
> unreachable, so `pytest` still works on a machine with no database.

**Available fixtures** (from [`tests/e2e/conftest.py`](tests/e2e/conftest.py)):

| Fixture | What it gives you |
| --- | --- |
| `client` | `ASGIClient` bound to the real app and the session loop |
| `register` | `register("alice", "secret123") -> (payload, token)` |
| `auth_headers` | headers for an already-registered user |
| `clean_users` | autouse — empties the table around every test |
| `loop` | the session event loop, for direct DB queries |

**A typical test** — act over HTTP, assert on the envelope:

```python
def test_update_user_applies_a_partial_change(client, register):
    created, _ = register("alice")
    user_id = created["user"]["id"]

    response = client.put(f"/users/{user_id}", json={"username": "alice2"})

    assert response.status_code == 200
    assert response.json()["data"]["username"] == "alice2"
```

**Testing a guarded route** — take the token from `register`, or use
`auth_headers` when you do not care who the user is:

```python
def test_me_returns_the_token_owner(client, register):
    _, token = register("alice")
    response = client.get("/users/me", headers={"Authorization": f"Bearer {token}"})
    assert response.json()["data"]["username"] == "alice"


def test_me_requires_a_token(client):
    response = client.get("/users/me")
    assert response.status_code == 401
    assert response.json()["message"] == "Token not found"
```

**Assert the envelope, not just the payload.** These fields are the API
contract, so it is worth pinning them explicitly at least once per module:

```python
def test_error_shape(client):
    body = client.get("/users/me").json()
    assert list(body) == ["success", "data", "errors", "message"]
    assert body["success"] is False
    assert body["errors"] == ["Token not found"]
```

**Checking the database directly** — run the query on the session loop, since
the engine's pool is bound to it:

```python
from sqlalchemy import text
from src.utils.db_connection import engine

def test_user_row_is_written(client, register, loop):
    register("alice")

    async def count():
        async with engine.connect() as connection:
            return (await connection.execute(text("SELECT count(*) FROM users"))).scalar()

    assert loop.run_until_complete(count()) == 1
```

E2E tests are plain `def` — `ASGIClient` drives the loop for you. Only reach for
`async def` when you are awaiting something yourself.

---

### Recording a known bug

When you find a bug you are not fixing yet, write the test for the **correct**
behaviour and mark it `xfail(strict=True)`:

```python
@pytest.mark.xfail(
    reason="known issue: POST /users/ stores the password in plaintext",
    strict=True,
)
def test_create_user_should_hash_the_password(client):
    created = client.post("/users/", json={"username": "bob", "password": "pw"})
    assert created.json()["data"]["password"] != "pw"
```

`strict=True` is the point: the test reports as an expected failure today, and
becomes a **hard failure** the moment someone fixes the bug — which is your
prompt to delete the marker. The entries in [Known issues](#known-issues) are
recorded this way in
[`test_users_e2e.py`](tests/e2e/test_users_e2e.py).

---

### Conventions

* **Name tests as sentences** — `test_login_rejects_wrong_password`, not
  `test_login_2`. The failure output is read far more often than the code.
* **One behaviour per test.** If the name needs "and", split it.
* **Arrange / act / assert**, separated by a blank line.
* **Assert on values, not just status codes** — a 200 with the wrong body still
  passes a status-only assertion.
* **Use `@pytest.mark.parametrize`** for the same assertion over several inputs:

  ```python
  @pytest.mark.parametrize(
      "path,expected",
      [("/none", None), ("/bool", False), ("/int", 42)],
  )
  def test_non_dict_payloads_do_not_crash(client, path, expected):
      assert client.get(path).json()["data"] == expected
  ```

* **Prove a test can fail.** After writing one, break the code briefly and
  confirm it goes red — a test that cannot fail is worse than no test, because
  it reads as coverage.

---

### How the setup works (and its limits)

Three pieces exist because `pytest-asyncio` and `httpx` could not be installed
in this environment. Swap them for the real packages whenever you can — the
tests themselves will not change.

* **`async def` tests** are run by a `pytest_pyfunc_call` hook in
  [`tests/conftest.py`](tests/conftest.py) instead of `pytest-asyncio`. Each unit
  test gets a fresh event loop.
* **[`tests/asgi_client.py`](tests/asgi_client.py)** replaces Starlette's
  `TestClient`, which requires `httpx`. It drives the app in-process over raw
  ASGI and exposes `get`/`post`/`put`/`delete` plus `.status_code`,
  `.headers`, `.json()` and `.text`.
* **E2E tests share one event loop** for the whole session. The async engine's
  connection pool is bound to the loop that opened its connections, so a
  per-test loop would fail on the second request.

Any module can be imported on its own — `tests/e2e/conftest.py` imports `main`
only because the e2e suite drives the real app, not to work around an import
cycle.

## Adding a new module

Using `todo` as the example (the directory is already scaffolded):

1. **Model** — `src/modules/todo/todo_model.py`, inheriting the shared `Base`:

   ```python
   from sqlalchemy import ForeignKey, String
   from sqlalchemy.orm import Mapped, mapped_column
   from src.utils.db_connection import Base

   class Todo(Base):
       __tablename__ = "todos"

       id: Mapped[int] = mapped_column(primary_key=True, index=True)
       title: Mapped[str] = mapped_column(String(200))
       user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
   ```

2. **DTOs** — `src/modules/todo/dtos/` for create and update payloads. Give every
   optional field an explicit `= None` default; in Pydantic v2, `Optional[str]`
   without a default is still **required**.

3. **Repository** — takes `db_factory` in `__init__`, opens a session per
   method.

4. **Service** — business rules; raises `HttpError` for failures.

5. **Controller** — a class owning an `APIRouter(prefix="/todos", tags=["Todos"])`.

6. **Register in the container** ([`src/utils/container.py`](src/utils/container.py)):

   ```python
   todo_repository = providers.Factory(TodoRepository, db_factory=db_factory)
   todo_service    = providers.Factory(TodoService, todo_repo=todo_repository)
   todo_controller = providers.Factory(TodoController, todo_service=todo_service)
   ```

   …and add `"src.modules.todo"` to the `WiringConfiguration` packages list.
   Do not add an `__init__.py` — see [Imports](#imports).

7. **Mount in** [`router.py`](router.py):

   ```python
   api_router.include_router(container.todo_controller().router)
   ```

8. **Import the model in `migrations/env.py`**, then autogenerate and apply the
   migration.

---

## Known issues

None outstanding — the items previously listed here (plaintext passwords on
`POST /users/`, password hashes in responses, unauthenticated CRUD routes, the
`500` that leaked database internals, missing-row `200`s, the fragile
`@Protected` decorator, the `__inti__.py` typo and the dotted `todo.*.py`
filenames) have all been fixed and have regression tests.

One thing to be aware of rather than a bug:

1. **`JWT_SECRET` in `.env.example` is a development placeholder.** Generate a
   real one before deploying (`python -c "import secrets; print(secrets.token_urlsafe(32))"`).
   PyJWT warns at runtime when the key is shorter than 32 bytes.
