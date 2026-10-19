# Release status

## Implemented: local intelligence workspace

Accounts and workspace roles; atomic queued CSV ingestion; local English sentiment; language detection; heuristic aspect/intent labels; statistical topic discovery; timeline and source dashboards; keyword brand comparisons; filtering and export; evidence research; human review and assignments; keyword alerts; saved and recurring reports; optional manual Bluesky collector; SQLite/PostgreSQL database support; Docker package and automated tests.

The interface deliberately uses ordinary browser JavaScript instead of adding a React build pipeline. The API uses FastAPI and SQLAlchemy. PostgreSQL and SQLite share the same application code. The queue and scheduler are durable database records processed by one application worker.

## Validation

The automated suite covers authentication/session logout, CSRF and host/origin controls, workspace isolation, roles, atomic import failure, deduplication, search/filter pagination, CSV formula protection, review/assignment/audit, alert deduplication, scheduled report creation, cited research, reanalysis preservation, and mocked social collection. Browser checks use synthetic local data. CI contains both SQLite and PostgreSQL jobs; inspect the actual Actions run before claiming remote checks passed.

## Remaining advanced roadmap

1. Multilingual transformer inference is implemented as an optional pinned local ONNX backend, with real inference smoke tests across five languages. Representative evaluation datasets, semantic embeddings and calibrated confidence remain future work.
2. Provider-approved integrations for additional social platforms, incremental synchronization and deletion propagation.
3. Statistical anomaly/crisis detection, with historical precision/recall validation; existing alerts are explicit count thresholds.
4. Generative research with verified evidence citations; the current assistant is extractive.
5. Password recovery, SSO, retention/deletion administration, schema migration tooling and stronger production administration.
6. Distributed workers/rate limiting, scalable analytical queries and dataset capacities beyond 5,000 posts.
7. Optional billing, email notifications and public hosting if requested later.

These are not represented as working features in the interface. The current delivery target is local/Docker, as selected by the project owner.
