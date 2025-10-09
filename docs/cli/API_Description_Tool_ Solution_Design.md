
# API Description Tool — Solution Design (Re-aligned 2025-09-17)

## 1. Architecture Overview
```
OpenAPI YAML
     │
     ▼
  parser.py  ──► flattener.py ──► tables.py ──► writer_excel.py / writer_csv.py
     ▲               │                    ▲                ▲
     │               └─ constraints      │                │
  cli.py ─ config.py ── validation ──────┘                │
     │                                                   tests/
```
- **cli.py** — argument parsing, config loading, validation toggle, orchestration.
- **config.py** — reads INI (`[input]`, `[output]`).
- **parser.py** — loads YAML and (optionally) validates it; higher-level traversal happens in `tables.py`.
- **flattener.py** — resolves `$ref`, merges `allOf`, folds `oneOf/anyOf` branches into a single object, extracts constraints.
- **tables.py** — builds rows for Params / Req Body / Res Body and applies “Mandatory” logic; implements **array asymmetry** (no primitive item row in request, do emit for response) and emits container rows for objects/arrays.
- **writer_csv.py / writer_excel.py** — persistence & formatting (bold for mandatory cells per SRS).
- **tests/** — unit, writer, CLI, integration.

## 2. Data Model (in‑memory)
```python
ParamRow  = {"name","mandatory","expected","in","description","examples"}
BodyRow   = {"status?" ,"path","property","mandatory","expected","description","examples"}
Tables    = {"params":[ParamRow], "req_body":[BodyRow], "res_body":[BodyRow]}
```
- `status` only for response rows.

## 3. Key Algorithms

### 3.1 `$ref` Resolution with Cycle Guard
- Maintain a `(doc_pointer, path_stack)` set.
- If `(ref_target in path_stack)`: note “(cycle)” and stop descent.
- Only **local** refs `#/components/...` are supported.

### 3.2 Combinators
- **allOf**: shallow merge `properties`, union `required`, scalars last‑writer‑wins.
- **oneOf/anyOf**: union visible properties into a single synthetic object (no additional note is appended to rows).

### 3.3 Constraint Extraction
- Map schema keywords to the compact string in SRS FR5.
- Derive types from `type` or simple `$ref` targets.
- Arrays: emit `array<inner>` with optional `minItems`, `maxItems`, and `unique` flags; `inner` prefers `type` or inline enum summary.
- Objects: mention `additionalProperties` rules.
- Enums are **not truncated**.

### 3.4 Traversal to Build Body Tables
- DFS with JSONPath-like addresses (`/customer/address[0]/street` for arrays).
- **Request**: suppress primitive array item row.
- **Response**: emit primitive array item row.

### 3.5 Parameters Table
- Iterate each operation’s `parameters` list (path-level inheritance is not materialised at this stage).
- `Mandatory` mirrors the parameter’s `required` flag; no implicit enforcement for path parameters beyond what the spec declares.
- `Expected Value(s)` is derived from the parameter’s schema.
- Examples use the parameter-level `example` field when present.

## 4. Output Writers
### CSV
- `Params`, `Req Body`, `Res Body` → three separate files (`<base>_params.csv`, etc.).
- UTF‑8, `\n` newlines, delimiter `,`, header row always present.

### Excel
- One workbook, three sheets.
- Bold styles when `mandatory=True`:
  - Params: **Name**
  - Req/Res: **Path** and **Property**
- CLI injects a blank row with the correct headers when a table would otherwise be empty so the writers always output at least a header row.

## 5. Config & Precedence
Order: CLI positional `output_file` → `config.output.file_name` (if not default) → `<input_stem>_api_tab_desc`.

## 6. Validation Flow
- If `[input] validate=True`, run `openapi-spec-validator`. On failure: **abort** (no `--force`).

## 7. Error Handling
- YAML load errors → friendly message.
- Missing content or non‑JSON → silently skipped; processing continues for other sections.
- Unknown keywords → ignored.

## 8. Testing Strategy
- **Unit**: `flattener`, `tables` (required, combinators, arrays).
- **Writer**: headers, bold formatting, CSV column order.
- **CLI**: precedence of output base, config loading.
- **Integration**: two real-world YAMLs in `tests/data` with stable snapshot counts.

## 9. Performance & Limits
- Traversal dominates; cycle guards prevent infinite loops.
- No network I/O; single-file YAML only.

## 10. Extensibility
- Potential backlog items (not yet implemented modules): example payload synthesis, HTML export, diff engine.
- Resolver for external refs (deferred until requested).
- i18n for column captions (deferred).

## 11. Security
- Safe YAML parsing; no code execution.
- No external fetching.

## 12. Deployment & CI
- GitHub Actions `tests.yml`, Python 3.10–3.12.
- Optional linting (ruff/flake8) future addition.

## 13. Decisions Confirmed (2025-09-17)
- **oneOf/anyOf**: union of properties without additional labelling.
- **Examples**: property-level only; no media-type examples.
- **Validation**: abort on failure; no `--force`.
- **External $ref**: not needed.
- **CSV delimiter**: `,` only.
- **Localization**: not required.
- **Array asymmetry**: yes.
- **Enums**: full list, no truncation.

## 14. Change Log
- 2025-09-17 (rev B): Reconciled module responsibilities, combinator handling, constraint strings, and empty-table behaviour with the current implementation.
- 2025-09-17: Incorporated user decisions; clarified examples handling, validation behavior, enums, and array asymmetry.
