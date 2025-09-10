# API Description Tool

Convert **OpenAPI 3.x YAML** into clean, human-readable **Params / Request Body / Response Body** tables in **CSV** or **Excel**. Designed so both technical and non-technical folks can read your API specs quickly — and so you can keep them updated fast after each epic.

## Highlights

* ✅ **OpenAPI 3.x** YAML → tables
* ✅ Safe **\$ref** resolution with cycle guards
* ✅ Smart **constraints extraction** (type, enum, min/max, minLen/maxLen, pattern, array limits…)
* ✅ **Excel formatting**: mandatory fields are bold (**Params → Name; Req/Res → Path & Property**)
* ✅ **Filename autoderived** from input (e.g., `my_api.yaml` → `my_api_api_tab_desc.xlsx`)
* ✅ **Tests**: unit + CLI + Excel/CSV writer + two **integration** tests for real specs
* ✅ **CI**: GitHub Actions workflow (`.github/workflows/tests.yml`) runs pytest on push/PR

---

## Quick Start

```bash
# clone & enter
git clone https://github.com/<YOUR_GH_USER>/api-description-tool.git
cd api-description-tool

# optional: create venv
python -m venv .venv
source .venv/bin/activate  # Windows: .\.venv\Scripts\Activate.ps1

# install
python -m pip install -U pip
python -m pip install -r requirements-dev.txt
python -m pip install -e .
```

Create a minimal `config.ini` (optional):

```ini
[input]
validate=True

[output]
format=xlsx
# file_name=api_tab_desc  # leave default; see filename rule below
```

Run:

```bash
# Excel (default base name derives from input filename)
python -m api_description_tool.cli path/to/openapi.yaml --config config.ini

# CSV (three files: _params.csv, _req_body.csv, _res_body.csv)
python -m api_description_tool.cli path/to/openapi.yaml outbase --config config.ini
```

---

## CLI

```
python -m api_description_tool.cli <input_file> [output_file] [--config CONFIG]
```

* `input_file` — path to your OpenAPI YAML.
* `output_file` (optional) — **base name** to write (without extension for CSV; `.xlsx` added for Excel).
* `--config` — path to `config.ini` (default: `config.ini` in CWD).

### Config options

```ini
[input]
validate=True        ; True/False — use openapi-spec-validator

[output]
format=csv           ; csv|xlsx
file_name=api_tab_desc
```

### Output filename rule (precedence)

1. **Positional** `output_file` argument (if provided)
2. `config.output.file_name` **when it’s not** `api_tab_desc`
3. Otherwise: **derived** from input filename → `<input_stem>_api_tab_desc`

Examples:

* `python -m ... my_api.yaml` → `my_api_api_tab_desc.xlsx`
* `python -m ... my_api.yaml outbase` → `outbase.xlsx`
* `file_name=final_tables` → `final_tables.xlsx`

---

## What the tool produces

### CSV

* `<base>_params.csv` with columns:
  `Name | Mandatory | Expected Value(s) | In | Description | Examples`
* `<base>_req_body.csv` with columns:
  `Path | Property | Mandatory | Expected Value(s) | Description | Examples`
* `<base>_res_body.csv` with columns:
  `Status | Path | Property | Mandatory | Expected Value(s) | Description | Examples`

### Excel

Workbook with three sheets: **Params**, **Req Body**, **Res Body** (same columns as above).

**Formatting:**

* If `Mandatory=True`:

  * **Params**: **Name** is bold
  * **Req Body / Res Body**: **Path** and **Property** are bold

---

## Constraints extraction

`Expected Value(s)` is a compact string, e.g.:

* `string minLen=2 maxLen=5 pattern=^[A-Z]+$`
* `integer min=1 max=10`
* `array<string> minItems=1`
* `string enum=a,b,c`

---

## Behavior & limits

* `$ref` resolution: **local** refs (e.g., `#/components/schemas/X`) with cycle detection.
* `allOf/oneOf/anyOf`: minimal, practical merge (properties + required) to keep tables useful.
* Arrays:

  * Request: no separate row for primitive array items (keeps tables compact)
  * Response: **does** emit a row for primitive array items (e.g., `/kinds[0]`)
* Empty specs or sections still produce files with headers.

---

## Project layout

```
api_description_tool/
  cli.py
  config.py
  parser.py
  flattener.py
  tables.py
  writer_csv.py
  writer_excel.py
tests/
  conftest.py
  test_config.py
  test_parser.py
  test_tables.py
  test_writer_csv.py
  test_writer_excel.py
  test_cli.py
  test_integration_specs.py
  data/
    alt-trans-an.yml
    psc_an.yml
.github/
  workflows/
    tests.yml
```

---

## Tests

```bash
# run everything
pytest -q

# only integration tests (with your real YAMLs under tests/data)
pytest -q -k "integration"
```

* Tested on Python **3.10 / 3.11 / 3.12** (GitHub Actions matrix).
* Windows PowerShell note: it doesn’t support `&&` on older PS versions. Use separate lines or `;`.

---

## CI

GitHub Actions workflow **`tests.yml`** runs the suite on every push/PR.
Matrix: Python 3.10–3.12.

---

## Troubleshooting

* **PowerShell error** “`The token '&&' is not a valid statement separator`”
  Run commands separately or use `;` (or upgrade to PowerShell 7+).
* **Validation errors**: set `[input] validate=False` to skip schema validation and still generate tables (useful for WIP specs).
* **No output files**: the tool inserts a minimal row to ensure writers create files even when a section has no rows.

---

## Contributing

PRs welcome! Please:

* Add/update tests for changes.
* Keep `flattener.py` as the place for recursion/constraints logic.
* Run `pytest -q` locally before opening a PR.

---

## License

MIT

---

## Credits

Built by a BA+Python workflow to accelerate API documentation after each epic.
