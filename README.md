# Social Ear

A social conversation intelligence platform, starting with a working local research prototype.

## Run

Requires Python 3.12 or newer. No third-party dependencies.

```sh
python -m app.server
```

Open http://127.0.0.1:8000. Import `examples/conversations.csv` to explore the dashboard. Example records are synthetic and are never loaded automatically. Data persists in `data/social-ear.db` (ignored by Git).

## Available now

- CSV ingestion with required `text` and optional `source`, `published_at` columns
- Transactional SQLite persistence, duplicate detection, blank row handling
- Search and sentiment filtering with matching dashboard statistics
- Transparent English keyword sentiment and recurring-word counts
- CSV export of filtered evidence, with spreadsheet formula protection
- Responsive dashboard, empty states, import feedback
- HTTP and ingestion tests, GitHub Actions CI

## Current limits

This is a local prototype, not the completed advanced platform. Sentiment is an intentionally simple English heuristic, not a trained model; neutral includes unknown languages. Recurring words are not semantic topics. There are no live social integrations, accounts, workspaces, LLM summaries, alerts, or background workers yet. The server binds only to localhost. Do not expose it publicly: production authentication, authorization, request hardening, pagination, and deployment infrastructure remain to be built. Imports are limited to 2 MB; this version loads matching posts into memory.

## Verify

```sh
python -m unittest discover -s tests -v
node --check web/app.js
```

## Architecture

`web/` contains the browser interface; `app/server.py` exposes same-origin HTTP endpoints; `app/store.py` owns SQLite ingestion; `app/analysis.py` defines the replaceable analysis baseline. No API keys are required. Never commit credentials, imported customer data, or database files.

## Next milestones

See [the roadmap](docs/ROADMAP.md). First prove the import-to-insight workflow, then migrate to a production API and add measured AI capabilities.
