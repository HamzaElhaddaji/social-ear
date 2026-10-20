# Run and deploy

## Windows / local

```powershell
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt
.venv/Scripts/python -m app
```

Open http://127.0.0.1:8000 and create an account. Passwords require 12 characters. Import `examples/conversations.csv`. Use ISO 8601 timestamps for dated charts; empty dates use ingestion time in the chart. Monitor alerts use published time, falling back to ingestion time, and examine only the latest 24 hours. The sample file has fixed dates, so it will not always trigger current alerts.

Use `python -m app` for the authenticated platform. The old launch command `python -m app.server` now starts this same authenticated application. The old handler implementation is retained only for regression tests. The new database is separate (`data/platform.db`). Re-import your original CSV into an authenticated workspace to migrate prototype data.

## Docker with PostgreSQL

Copy `.env.example` to `.env`, set a unique `POSTGRES_PASSWORD`, start Docker Desktop, then run:

```sh
docker compose up --build -d
```

The app listens at http://localhost:8000. PostgreSQL is not exposed to the host. Database data persists in a named Docker volume. Never commit `.env`.

## Internet hosting

Run one application process/replica. The durable queue, scheduler and authentication rate limiter currently assume a single process. A multi-process deployment requires an external worker queue and shared rate limiter first. Set `PUBLIC_ORIGIN=https://your-domain` and `ALLOWED_HOSTS=your-domain`. Terminate TLS at a reverse proxy, set `COOKIE_SECURE=1`, and route traffic to port 8000. Set `ALLOW_REGISTRATION=0` after enrolling your initial team if public registration is unwanted. There is no email verification, password reset email, or SSO yet.

Language detection, sentiment and TF-IDF/K-means run locally. Optional [Groq research](GROQ.md) uses a hosted API and is subject to your provider plan and quota; it does not upgrade billing automatically. Dataset size is bounded to 5,000 posts per workspace. Imports are atomic and limited to 2 MB. Topic analysis is computed on filtered data; filters may produce different clusters.

## Public social collection

Set `ENABLE_BLUESKY=1` to expose the manual Bluesky collector. Search is capped at 100 latest posts. Optional Mastodon hashtag collection and YouTube video comments are also implemented; see [connector configuration](SOCIAL_CONNECTORS.md). Each source is disabled by default and depends on provider availability, permissions and credentials. No provider request is made while disabled. Imported conversation data is not sent to the social providers.

## Jobs, schedules and recovery

Imports, reports and collection are persisted jobs. The built-in worker checks pending jobs once per second. Interrupted running jobs are re-queued on application restart; import deduplication prevents duplicate posts. Failed jobs can be retried up to three attempts from the UI. A scheduled report runs at most once per configured interval; missed intervals coalesce to one report after restart. Reports are stored snapshots; no email is sent. Alerts are in-app threshold signals, not predictive crisis detection.

## Backups and restoration

SQLite: stop the app, copy `data/platform.db` to a secure location, then restart. Restore by stopping the app and replacing that file with the backup. PostgreSQL: use `pg_dump`/`pg_restore` through your hosting backup system, and test restoration before production use. Exports and reports do not include accounts or all audit records and are not database backups.

## Schema

This is the first relational platform schema. SQLAlchemy creates missing tables at startup. It does not automatically alter existing tables; future schema changes require an explicit migration and backup. PostgreSQL CI exercises the same integration suite. Do not point it at an unrelated application database.

## Verification and limits

```sh
python -m unittest discover -s tests -v
node --check web/app.js
```

Tests cover authentication, workspace isolation, CSRF, role enforcement, atomic imports, duplicates, filters, review, alerts, scheduling, report evidence, hosted-request redaction and mocked collection/generation. Optional [multilingual inference](MULTILINGUAL.md) has real CPU smoke tests when installed. Generation supports Ollama or a configured Groq API key; a live Groq synthetic-evidence test has passed. Live YouTube collection requires a valid API key. Password recovery, retention/deletion workflows and billing are not implemented.
