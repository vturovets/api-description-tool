
# API Description Tool — Solution Design (Updated 2025-09-17)

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
- **parser.py** — loads YAML, path/operation enumeration, request/response media selection.
- **flattener.py** — resolves `$ref`, merges `allOf`, **unions** `oneOf/anyOf` properties with a note, extracts constraints.
- **tables.py** — builds rows for Params / Req Body / Res Body and applies “Mandatory” logic; implements **array asymmetry** (no primitive item row in request, do emit for response).
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
- **allOf**: deep‑merge `properties`, union `required`, scalars last‑writer‑wins.
- **oneOf/anyOf**: **union** visible properties and attach note “oneOf/anyOf” (no path explosion).

### 3.3 Constraint Extraction
- Map schema keywords to the compact string in SRS FR5.
- Derive types from `type` or `$ref`.
- Arrays: include `items=<type|$ref-name> minItems=<n> maxItems=<m>`.
- Objects: mention `additionalProperties` rules.
- Enums are **not truncated**.

### 3.4 Traversal to Build Body Tables
- DFS with JSONPath-like addresses (`/customer/address[0]/street` for arrays).
- **Request**: suppress primitive array item row.
- **Response**: emit primitive array item row.

### 3.5 Parameters Table
- Iterate `paths/*/*/parameters` plus inherited `pathItem.parameters` (OpenAPI merge rules).
- `mandatory = True` for `required=True` or for any path param.
- `expected` from param `schema` constraints and `enum`.
- Examples: property-level only.

## 4. Output Writers
### CSV
- `Params`, `Req Body`, `Res Body` → three separate files (`<base>_params.csv`, etc.).
- UTF‑8, `\n` newlines, delimiter `,`, header row always present.

### Excel
- One workbook, three sheets.
- Bold styles when `mandatory=True`:
  - Params: **Name**
  - Req/Res: **Path** and **Property**

## 5. Config & Precedence
Order: CLI positional `output_file` → `config.output.file_name` (if not default) → `<input_stem>_api_tab_desc`.

## 6. Validation Flow
- If `[input] validate=True`, run `openapi-spec-validator`. On failure: **abort** (no `--force`).

## 7. Error Handling
- YAML load errors → friendly message.
- Missing content or non‑JSON → skip with warning but continue with other sections.
- Unknown keywords → ignored or added as notes when feasible.

## 8. Testing Strategy
- **Unit**: `flattener`, `tables` (required, combinators, arrays).
- **Writer**: headers, bold formatting, CSV column order.
- **CLI**: precedence of output base, config loading.
- **Integration**: two real-world YAMLs in `tests/data` with stable snapshot counts.

## 9. Performance & Limits
- Traversal dominates; cycle guards prevent infinite loops.
- No network I/O; single-file YAML only.

## 10. Extensibility
- Example payload synthesis (`examples.py`), HTML export (`writer_html.py`), diff engine (`diff.py`).
- Resolver for external refs (deferred until requested).
- i18n for column captions (deferred).

## 11. Security
- Safe YAML parsing; no code execution.
- No external fetching.

## 12. Deployment & CI
- GitHub Actions `tests.yml`, Python 3.10–3.12.
- Optional linting (ruff/flake8) future addition.

## 13. Decisions Confirmed (2025-09-17)
- **oneOf/anyOf**: union with note.
- **Examples**: property-level only; no media-type examples.
- **Validation**: abort on failure; no `--force`.
- **External $ref**: not needed.
- **CSV delimiter**: `,` only.
- **Localization**: not required.
- **Array asymmetry**: yes.
- **Enums**: full list, no truncation.

## 14. Change Log
- 2025-09-17: Incorporated user decisions; clarified examples handling, validation behavior, enums, and array asymmetry.
