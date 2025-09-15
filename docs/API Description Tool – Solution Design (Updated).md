
# API Description Tool — Solution Design (Updated 2025-09-15)

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
- **flattener.py** — resolves `$ref`, merges `allOf`, minimal `oneOf/anyOf`, extracts constraints.
- **tables.py** — builds rows for Params / Req Body / Res Body and applies “Mandatory” logic.
- **writer_csv.py / writer_excel.py** — persistence & formatting.
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
- On visiting a `$ref`, if `(ref_target in path_stack)`: emit note “(cycle)” and stop descent.
- Resolve only **local** refs `#/components/...`.

### 3.2 Combinators
- **allOf**: deep‑merge `properties` (later entries override scalar constraints), union `required`.
- **oneOf/anyOf**: collect union of visible properties and attach note “oneOf/anyOf”. Avoid exploding combinations.

### 3.3 Constraint Extraction
- Map schema keywords to the compact string in SRS FR5.
- Derive types from `type` or `$ref` target name.
- Arrays: include `items=<type|$ref-name> minItems=<n> maxItems=<m>` when present.
- Objects: mention `additionalProperties` rules (boolean or schema name).

### 3.4 Traversal to Build Body Tables
- DFS with a `path` stack producing JSONPath-like addresses (`/customer/address[0]/street` for arrays).
- **Request**: do **not** produce extra primitive array item row (compactness).
- **Response**: do produce a primitive array item row.

### 3.5 Parameters Table
- Iterate `paths/*/*/parameters` plus `pathItem.parameters` with OpenAPI merge rules.
- `mandatory = True` when `required=True` or param is a path param (OpenAPI rule).
- `expected` from param `schema` constraints and `enum`.

## 4. Output Writers
### CSV
- `Params`, `Req Body`, `Res Body` → three separate files (`<base>_params.csv`, etc.).
- UTF‑8, `\n` newlines, header row always present.

### Excel
- One workbook, three sheets.
- Bold styles when `mandatory=True`:
  - Params: **Name**
  - Req/Res: **Path** and **Property**

## 5. Config & Precedence
Order: CLI positional `output_file` → `config.output.file_name` (if not default) → `<input_stem>_api_tab_desc`.

## 6. Validation Flow
- If `[input] validate=True`, run `openapi-spec-validator`.
- On failure: abort with non‑zero exit (current). Roadmap: `--force` to proceed with warnings.

## 7. Error Handling
- YAML load errors → friendly message with filename.
- Missing content or non‑JSON → skip with warning but keep generating other sections.
- Unknown keywords → ignored but preserved in notes when feasible.

## 8. Testing Strategy
- **Unit**: `flattener`, `tables` edge cases (required, combinators, arrays).
- **Writer**: headers, bold formatting (inspecting cell styles), CSV column order.
- **CLI**: precedence of output base, config loading.
- **Integration**: two real-world YAMLs in `tests/data` produce stable snapshots (row counts ≥ 1).

## 9. Performance & Limits
- Time complexity dominated by schema traversal; cycle guards prevent infinite loops.
- Memory proportional to schema size; typical spec (< 2 MB) fits easily.
- No network calls; local file only.

## 10. Extensibility
- Plug‑in extraction for examples (`examples.py`), HTML export (`writer_html.py`), diff engine (`diff.py`).
- Add `Resolver` to support external refs (filesystem/HTTP) behind a flag.
- Internationalization layer for column captions via config mapping.

## 11. Security
- No code execution of untrusted content. YAML parsed safely.
- Do not follow external URLs unless explicit feature flag is enabled.

## 12. Deployment & CI
- GitHub Actions workflow `tests.yml`, Python 3.10–3.12.
- Lint (optional): ruff/flake8 could be added later.

## 13. Open Questions / Clarifications
1. **`oneOf/anyOf` rendering**: keep union of properties with note — acceptable?  
2. **Examples**: prefer `example`/`examples` at property vs media-type example?  
3. **Abort vs continue on validation failure**: should we implement `--force` now?  
4. **External `$ref`** support priority (file/HTTP)?  
5. **CSV delimiter** is `,` — need `;` option for EU locales?  
6. **Localization**: translate column headers via config?  
7. **Response primitive array rule** confirmed (emit item row), request side suppressed?  
8. **Enum formatting**: truncate long enum lists or wrap?  
9. **AdditionalProperties**: include in `expected` string or separate column?

## 14. Change Log
- 2025-09-15: Aligned SRS & Design with current code and README; clarified precedence rules, constraints string, bolding rules, and array item emission asymmetry.
