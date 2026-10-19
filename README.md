# Social Ear

A local conversation intelligence application for importing social feedback, exploring evidence, monitoring issues, and working as a team.

## Quick start

Python 3.12 is required. On Windows, run `./start.ps1`, or use:

```sh
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt
.venv/Scripts/python -m app
```

On Linux/macOS, use `.venv/bin/python` instead. Open http://127.0.0.1:8000 and create an account. Import `examples/conversations.csv` to begin. Data persists in `data/platform.db` and is ignored by Git.

For a populated local demo, run `.venv/Scripts/python -m app.demo`. It creates only synthetic records in the default local SQLite database. Demo login: `demo@social-ear.test` / `Local-demo-only-2026!`. Never run the demo seed on an internet-facing installation.

## Implemented

- Accounts, scrypt password hashing, expiring server-side sessions, logout
- Multiple workspaces, owner/analyst/viewer roles, tenant-scoped access
- Background CSV imports, atomic persistence, duplicate detection, job history and retries
- English VADER sentiment with versioned product-support rules, language detection, aspect estimates, intent tagging
- TF-IDF/K-means topic discovery, timeline charts, source comparisons and keyword-based brand comparisons
- Search, sentiment/source/date filters, pagination, safe CSV export
- Evidence research assistant with original-post citations and explicit extractive behavior
- Human sentiment corrections, issue assignment, investigation status, team notes and audit history
- Rolling 24-hour keyword/threshold monitors, deduplicated in-app alerts and acknowledgement
- Saved JSON reports and recurring report schedules
- Optional manual Bluesky public-search collection, disabled by default
- SQLite locally, PostgreSQL configuration, non-root Docker image and Compose package
- Integration tests and GitHub Actions jobs for SQLite, PostgreSQL and JavaScript syntax

## Docker

Start Docker Desktop. Copy `.env.example` to `.env`, set a unique `POSTGRES_PASSWORD`, then:

```sh
docker compose up --build -d
```

Open http://localhost:8000. See [deployment instructions](docs/DEPLOYMENT.md) for configuration, backups and operational limits. Docker requires a running Linux engine; source and Compose configuration alone do not confirm a successful container deployment.

## Analysis boundaries

Sentiment defaults to VADER plus explicit English domain rules. An optional, pinned local ONNX transformer supports eight languages; see [multilingual setup](docs/MULTILINGUAL.md). Unsupported languages remain unclassified. Very short posts may have undetermined language. Scores are estimates, not calibrated confidence. Aspect and intent labels remain heuristic. Topic clusters are statistical and may change with filters.

The assistant retrieves related posts and computes a sentiment summary. It is not a generative chatbot and does not infer causes beyond the evidence. External AI services are not used. Bluesky collection has mocked test coverage and depends on provider availability; Instagram, X, Facebook and Reddit integrations are not included.

## Verification

```sh
python -m unittest discover -s tests -v
node --check web/app.js
```

Install dependencies first. Set `TEST_DATABASE_URL` to a dedicated PostgreSQL database to run platform tests against it; each test uses an isolated temporary schema. Never use a production database for test execution. `requirements.lock` records the tested environment; `requirements.txt` lists pinned direct dependencies.

## Structure

| Path | Purpose |
| --- | --- |
| `app/api.py` | Authenticated FastAPI endpoints, roles and request validation |
| `app/database.py` | SQLAlchemy tables and database session factory |
| `app/service.py` | Ingestion, durable jobs, schedules, alerts, reports |
| `app/intelligence.py` | Local analysis, topic clustering, research retrieval |
| `app/connectors.py` | Optional fixed-endpoint Bluesky collector |
| `web/` | Responsive interface with no frontend build step |
| `tests/` | Original regression tests and platform integration coverage |

The original storage/handler modules remain for regression tests. The original launch command now starts the authenticated application. Prototype data is not automatically mixed into account workspaces; re-import your CSV to migrate.

## Scope

This release targets local/single-server use. Run one API process because the worker, scheduler and authentication rate limiter assume one process. Dataset capacity is 5,000 posts per workspace; uploads are limited to 2 MB. There is no SSO, email password recovery, billing, retention automation, predictive crisis model or public hosted service. See [release status and next steps](docs/ROADMAP.md).
