Executable implementation plan (rich web UI)
Phase 0 — Confirm scope + align with existing capabilities
Goal: ensure the UI plan matches current conversion logic and web requirements.
Actions:

Reconfirm that the UI must reuse the existing conversion pipeline and filename rules (no logic changes).

Confirm frontend stack = React + Tailwind (per clarifications).

Exit criteria: Written agreement on scope and stack; no backend logic changes to conversion pipeline.

Phase 1 — Backend API completion (conversion + job lifecycle)
Goal: implement the missing API endpoints and job workflow needed for the UI.
Current foundation: Upload + health exist, settings already cover TTL, size, and job limits.

Actions:

Define API models for convert requests, job status, metrics, and errors.

Extend web/backend/models.py with job/convert/metrics schemas to match CR‑002 response payloads.

Implement POST /api/convert:

Validate upload_id, path, method (if required), format, validate.

Enforce concurrency from Settings.max_concurrent_jobs and job_timeout_seconds.

Run the existing conversion pipeline in-process (per CR‑002) using the same modules as CLI, producing output in temp storage.

Implement GET /api/job/{job_id}:

Return status, logs, metrics, and download URL when ready.

Implement GET /api/download/{job_id}:

Serve generated xlsx or zipped csv files (naming per precedence rules).

Implement DELETE /api/job/{job_id}:

Remove artifacts and clean state. (Matches CR‑002 lifecycle.)

Error handling mapping:

Map errors to CR‑002 error codes + HTTP statuses (YAML syntax, validation failure, path/method missing, file too large, etc.).

Exit criteria: API endpoints match CR‑002 spec and can be exercised via curl/Postman.

Phase 2 — Job storage, logging, and retention strategy
Goal: implement rich job logging and TTL cleanup compatible with UI progress.

Actions:

Job state store:

Introduce an in-memory or file-based job registry (status, logs, metrics, paths to artifacts).

Log capture:

Append pipeline events to a per-job log buffer (for /api/job/{job_id} polling).

Artifact storage:

Use storage.ensure_upload_dir to keep outputs under the existing temp root; include CSV zip support and xlsx placement.

Retention:

Keep existing janitor strategy; ensure job registry entries are deleted when directories are removed (TTL).

Exit criteria: Jobs and logs survive long enough for UI polling and are removed after TTL.

Phase 3 — Frontend UI (React + Tailwind) for rich interaction
Goal: implement the full upload → inspect → select → convert → download flow.

Actions:

Scaffold frontend (e.g., Vite + React + Tailwind), configured to serve a single SPA page.

Primary screens/components:

Upload panel with drag-and-drop, size checks, and retry status indicators.

Path/method selector with disabled Convert until inputs are valid; method required only if multiple methods exist.

Validation toggle and format selector (xlsx/csv).

Conversion progress + real-time log panel (poll /api/job/{job_id}) and row count display on completion.

Download button linking to /api/download/{job_id}.

Accessibility + UX:

Keyboard-accessible controls, clear focus states, ARIA for logs/progress, and footer with version/sha.

Exit criteria: UI can complete the end-to-end flow using the backend endpoints.

Phase 4 — Testing and regression alignment
Goal: ensure the web pipeline matches CLI outputs and core invariants.

Actions:

Backend unit tests for upload/convert/job/download endpoints and error mappings.

Integration regression tests using existing CLI fixtures for equivalence between web and CLI outputs.

UI testing (optional): smoke tests (Cypress/Playwright) for main flows.

Exit criteria: passing CI tests, output equivalence checks, documented coverage.

Phase 5 — Packaging and deployment
Goal: ship the UI + backend as a single deployable artifact.

Actions:

Dockerfile to build frontend assets and serve them (via FastAPI static or separate container) consistent with CR‑002 packaging intent.

Runtime security headers and no CORS (internal use).

Exit criteria: docker build + docker run produce a working UI and API.