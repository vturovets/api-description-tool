- **Frontend stack**: OK to proceed with React + Tailwind (as in CR-002), or do you prefer a server-rendered page for MVP? - React + Tailwind

- **Auth**: CR-002 says *none (internal use)*—confirm that stays true for Phase 1? - affirmative; internal use only.

- **Hosting target**: Docker on a single VM is fine—any constraints on ports, reverse proxy, or HTTPS termination? - nothing specific at the moment

- **Fixture specs**: which two YAMLs should be the canonical CLI↔Web regression fixtures in CI? (I can default to `tests/data` already in the repo.)  - CLI which is already in repo.

- **Versioning**: do you want the UI release tagged as `v1.0.0-web` (leaving CLI as `v0.9-cli`), or a single semantic version for both deliverables? - I have v0.1.0 called 'CLI version', perhaps v0.1.0-web would work.


