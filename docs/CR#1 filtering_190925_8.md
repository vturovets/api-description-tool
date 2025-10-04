# Change Request (CR-001): Endpoint Filtering for OpenAPI inputs

## 1) Background & Goals

You use the tool to turn OpenAPI 3.x YAML into spec tables that both tech and non-tech folks can read. Current pipeline (CLI → parse/flatten → tables → writers) doesn’t let you choose a subset of endpoints when a spec contains many paths. (Repo layout and CLI/config conventions summarized in the README. [GitHub](https://github.com/vturovets/api-description-tool))

**Goals**

- Add a filtering capability that selects the required OpenAPI `path` (and optionally HTTP method) **before** table generation.
- Keep existing behavior completely unchanged when no filters are configured.
- Minimize code surface touched:
  - New module: `api_description_tool/filter.py`
  - Tiny hook in CLI (one call) and **read config under a new `[filtering]` section** in `config.ini` (per your constraint).

**Non-Goals**

- No changes to writer formatting, column sets, or filename derivation rules (those remain per README). [GitHub](https://github.com/vturovets/api-description-tool)
- No re-ordering or merging of operations beyond filtering.
- No cross-file `$ref` or advanced spec slicing beyond path/method/tag predicates.

---

## 2) User Stories

1. **As a BA/PO**, I want to run the app to get a tabular description for the specified single endpoint from the YAML file containing OpenAPI 3.x descriptions of several endpoints (paths).

---

## 3) Functional Requirements

- FR-001: Read filter rules from `[filtering]` in `config.ini` (optional).
  
  Supported keys:
  
  `path` ; exact required path (including braces and trailing slashes) e.g., `/v1/packages/availability/departures`; optional;
  
  `method: GET,POST,…`; optional; `method` comparison is **case-insensitive** (e.g. `get`, `GET`) against OpenAPI operation keys;
  
  For specs with multiple paths/methods, both `path` **and** `method` must be specified.

- FR-002: If `[filtering]` is missing/empty **and** the spec has **exactly one path with exactly one method**, proceed without filtering (full backward compatibility). Otherwise, raise the FR-003 error.

- FR-003: If no filtering is provided and the spec has **more than one path** or has **one path with multiple methods**, raise an error: "Your spec contains multiple endpoints but no filtering rules. Add `[filtering]` with `path=` and `method=` in `config.ini`."

- FR-004: If `path` is specified and the selected path has **multiple methods**, and `method` is not specified, **raise an error**: "Multiple methods under the selected path; add `method=` in `[filtering]`".

- FR-005: If `path` is specified and the YAML file does not contain the requested path, raise an error with a comprehensive message (e.g. "Your spec does not contain the required path. Specify the correct path in the `[filtering]` section of `config.ini` with `path=`").

- FR-006: If `path` and `method` are specified, and the YAML file does not contain the requested path and method, raise an error with a comprehensive message (e.g. "Your spec does not contain either the required path or method. Specify the correct path and method in the `[filtering]` section of `config.ini`").

- FR-007: If `path` is either empty or missing and `method` is specified, raise an error with a comprehensive message ("The method cannot be specified alone. Please specify both path and method").

- FR-008: Filtering must work with OpenAPI 3.0/3.1 and leave unrelated sections untouched (`components`, `info`, etc.).

- FR-009: keep current `[input] validate=True/False` behavior as-is; filtering runs **before** parsing/tables but **after** YAML load.

- FR-010: If the spec has **one path with one method** and `[filtering]` is present but only `path` is provided (matching that path), proceed with filtering without explicitly specified method; applies only when the spec itself has exactly one path and one method (a trivial spec)

---

## 4) Config & CLI

- **Config**: keep current conventions, add a new section:
  
  ```
  [filtering]
  path=/v1/packages/availability/departures
  method=GET
  ```

- **CLI** (no flags required): existing `-config` is enough. The tool auto-applies filters when present (keeping your current CLI signature per README). [GitHub](https://github.com/vturovets/api-description-tool)

---

## 5) Design & Hook-in

- **New module**: `api_description_tool/filter.py` (pure functions, unit-tested).
- **Hook point**: in `cli.py` right **after** loading YAML into a Python dict and **before** calling parser/tables.
  - Import `apply_filters` and `load_filter_rules`.
  - If rules are non-empty, call `spec = apply_filters(spec, rules)`.

This uses the existing project layout and preserves all downstream logic and outputs (per README’s pipeline). [GitHub](https://github.com/vturovets/api-description-tool)

---

## 6) Backward Compatibility

- Default behavior unchanged when `[filtering]` missing or empty.
- No changes to output filenames, CSV/XLSX schemas, or formatting rules. [GitHub](https://github.com/vturovets/api-description-tool)

---

## 7) Testing

- **Unit tests**: `tests/test_filter.py` (new)
  - Path is presented
  - Path is missing, Method is presented
  - Path is not specified correctly
  - Method is not specified correctly
  - **FR-002 happy-path**: a spec with exactly one path & one method and **no** `[filtering]` → ensure pipeline runs with no filtering
  - Path-only + multi-method
  - trivial spec + `[filtering]` present with only `path` → succeeds and selects the sole method.
- **Integration test**: `tests/test_integration_filter_multi_paths.py`
  - Use the attached `multi_paths.yml` (place at `tests/data/multi_paths.yml`).
  - Run pipeline with a temp `config.ini` containing `[filtering]` rules.
  - Assert that only selected endpoints drive table generation (e.g., presence/absence of rows/paths in produced CSV/XLSX or, if simpler, assert against the filtered `path` dictionary prior to table build—see notes in the test code).
  - Assert that the error message is generated when `[filtering]` missing or empty.

---

## 8) Risks & Mitigations

- N/A

---

## 9) Rollout

- Add `filter.py`, tests, and `[filtering]` examples to `config_example.ini`.
- Minimal 2-line change in `cli.py` to insert the hook.

## 10) Additional clarifications

1. Wildcard matching: v1 hinted at globbing (include/exclude), but v2 removed this. If you do want wildcard/exclude later, the spec will need another CR. – fine with another CR when I need wildcard/exclude.

2. Error handling: v2 mandates raising errors in many cases — do you want to allow a “force” option (e.g. [input] validate=False) to bypass these errors, or should they always stop execution? – keep [input] validate=False remains **only** about OpenAPI 3.x schema/compliance checks. If `[filtering]` is present (i.e., not empty), always enforce filtering.

3. Multiple paths but no filter: v2 requires an error. Is this acceptable for your workflow, or would you prefer a “warn and continue with all paths” fallback? – yes, it is totally acceptable since I need a separate tabular presentation for each path.

4. Method-alone case (FR-007): currently forbidden. If in practice you sometimes want “all paths with GET methods”, that would require a future extension. – I don’t need all path with GET methods. One run -> one path, one method.

5. **Richer error messages**: no need so far.
