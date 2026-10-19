# Roadmap

## 1. Working foundation (this release)
CSV import, persistent posts, evidence search, baseline sentiment, dashboard, export, automated tests.

## 2. Production application foundation
Adopt a typed React/Next.js frontend and FastAPI service; migrate storage to PostgreSQL with migrations. Add accounts, organizations, roles, tenant isolation, pagination, structured logging, backups, deployment and integration tests. Keep the current prototype as a behavior reference, not a production server.

## 3. Evaluated intelligence
Introduce a provider interface and background job queue. Add language detection, evaluated multilingual sentiment, aspect sentiment and semantic topic clustering. Maintain a labeled evaluation dataset and report performance by language. AI summaries must cite source records; store model/version metadata and allow human correction. Require explicit configuration for external AI processing.

## 4. Social listening
Verify platform API access, permissions, quotas and retention rules before selecting integrations. Add connectors incrementally, incremental ingestion, retries, rate-limit handling, provenance and deletion propagation. Keep CSV available.

## 5. Monitoring and teamwork
Saved keyword monitors, time-series analysis, volume anomaly detection, alert deduplication, competitor comparisons, assignments and investigation history. Validate alerts on historical datasets before enabling notifications.

## 6. Professional delivery
Evidence-grounded research assistant, scheduled reports, audit logs, usage controls, optional billing, load testing, security review and production observability.

Each milestone should have acceptance criteria, a working demonstration and appropriate tests before expanding scope.
