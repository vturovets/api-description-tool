# API Description Tool — SRS v2 (Updated 2025-09-17)

## 1. Purpose & Context

This tool converts **OpenAPI 3.x YAML** files into compact, human‑readable tables for **Parameters**, **Request Body**, and **Response Body**, exportable as **Excel** or **CSV**. The goal is to (a) unify API descriptions consumable by both technical and non‑technical stakeholders, and (b) reduce time to create and maintain specs after each epic.

## 2. Scope

**In-scope**

- Parse a single OpenAPI 3.x YAML file.
- Resolve local `$ref` references with cycle detection.
- Flatten composed schemas (`allOf`, `oneOf`, `anyOf`) with a pragmatic merge to expose properties and `required` flags.
- Extract constraints into a compact **Expected Value(s)** string (type, enum, min/max, minLength/maxLength, pattern, array limits, item type).
- Generate **Excel** (single workbook, three sheets) or **CSV** (three files) with consistent column sets.
- Apply visual emphasis (bold) for mandatory fields.
- Filename auto-derivation from input stem unless overridden by CLI posarg or config.
- Optional OpenAPI validation (on/off) using `openapi-spec-validator`.
- Unit tests, writer tests, CLI tests, and two integration tests (sample YAMLs).

**Out-of-scope (current version)**

- Remote `$ref`/external URLs, multi-file specs.
- Full JSON Schema support (e.g., advanced `if/then/else`, custom formats).
- Content-negotiated variants per media type (first/JSON-only used heuristically).
- Example payload synthesis.
- HTML/portal doc generation (Redoc/Stoplight-level).

## 3. Users & Roles

- **BA / PO**: reads tables, annotates descriptions, shares with business.
- **Backend dev**: verifies schema, constraints, and required flags quickly.
- **QA**: uses tabular view for test design.

## 4. Functional Requirements

### FR1. CLI

- `python -m api_description_tool.cli <input_file> [output_file] [--config CONFIG]`  
- If `output_file` is omitted, Excel name follows the **filename rule** (see FR4).  
- `--config` points to INI with `[input]` & `[output]` sections.

### FR2. Configuration

- `[input] validate=True|False` — run `openapi-spec-validator`.
- `[output] format=csv|xlsx`
- `[output] file_name=<base>` — when not equal to default (`api_tab_desc`), overrides base name.
- CSV delimiter is fixed to `,` (no localization at this time).

### FR3. Tables

**Common columns**

- Params: `Name | Mandatory | Expected Value(s) | In | Description | Examples`
- Req Body: `Path | Property | Mandatory | Expected Value(s) | Description | Examples`
- Res Body: `Status | Path | Property | Mandatory | Expected Value(s) | Description | Examples`

**Population rules**

- **Parameters**: enumerate across paths+operations (`in` in `{{query,header,path,cookie}}`); required → `Mandatory=True`.
- **Request Body**: traverse JSON schema; `Mandatory=True` when property in `required` or array `minItems>0` for item presence.
- **Response Body**: same as request; include **Status** from responses. For primitive arrays, emit a row for the item (e.g., `/items[0]`).

**Formatting**

- Excel: if `Mandatory=True` → **bold**: Params: **Name**, Req/Res: **Path** and **Property**.

### FR4. Output filename rule (precedence)

1. Positional `output_file` argument (if provided).  
2. `config.output.file_name` when it’s not the default `api_tab_desc`.  
3. Derived from input filename: `<input_stem>_api_tab_desc`.

### FR5. Constraints extraction (“Expected Value(s)”)

- Base: `type` (string, integer, number, boolean, object, array).
- String: `minLen`, `maxLen`, `pattern`, `enum`.
- Number/Integer: `min`, `max`, `exclusiveMin`, `exclusiveMax`, `multipleOf`.
- Array: `items=<type or $ref name>`, `minItems`, `maxItems`, `uniqueItems`.
- Object: `additionalProperties` (boolean or schema name).
- Present `enum` as comma-separated list **without truncation**.
- Merge across `allOf` (union of `properties`, union of `required`; last-write-wins for scalar constraints). `oneOf/anyOf`: **union of properties** with a note “oneOf/anyOf” (no combinatorial expansion).

### FR6. Validation

- When `validate=True`, run OpenAPI schema validation; on failure, **abort** (no `--force` yet).

### FR7. Examples

- Prefer **property-level** `example`/`examples` where present. No media-type examples are considered.

### FR8. Empty sections

- Writers create files/sheets with headers even if no rows were discovered.

### FR9. CSV & Excel writers

- CSV: three files, UTF‑8 with newline `\n` and delimiter `,`.
- Excel: one workbook with three sheets named `Params`, `Req Body`, `Res Body`.

### FR10. Logging & UX

- CLI prints: input file, output base, format, validation on/off, row counts per section.

## 5. Non‑Functional Requirements

- **Compatibility**: Python 3.10–3.12 (CI matrix).
- **Performance**: ≤3s for typical specs <2 MB on laptop; recursion safeguards for cycles.
- **Reliability**: cycle guards for `$ref`; minimal merges for combinators.
- **Testability**: pytest suite; integration tests with `tests/data/*.yml`.
- **Portability**: Windows/Unix shells (note on PowerShell `&&`).

## 6. Assumptions & Decisions

- Prefer `application/json` content; fall back to first media type when JSON missing.
- **Array asymmetry**: request does **not** add a separate primitive item row; response **does**.
- “Mandatory” derived from `required`, path params implied required by spec.
- Examples: property-level only.

## 7. Error Handling

- Invalid YAML → clear message.
- Missing media type → skip with warning.
- Unsupported keywords retained silently in notes where sensible.

## 8. Risks

- Complex `oneOf/anyOf` may not flatten meaningfully.
- External refs not expanded (by design).

## 9. Testing

- Unit tests for parser & flattener.
- Writer tests validate headers, bold formatting on mandatory fields.
- CLI tests ensure precedence for output filename.
- Integration tests on two sample YAMLs under `tests/data`.

## 10. Roadmap (Change Requests candidates)

- Example payload synthesis (from schema).
- HTML portal export (single‑page, links per path).
- i18n (deferred).
- `--force` to continue after validation errors with warnings.
- Schema diffs across versions (breaking? reason) → table.

## 11. Glossary

- **Path**: JSONPath‑like traversal within schemas.
- **Property**: name at current level within `Path`.
- **Expected Value(s)**: compact constraints string described in FR5.
