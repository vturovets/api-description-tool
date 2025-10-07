# API Description Tool

Convert **OpenAPI 3.x YAML** files into concise, stakeholder-friendly tables covering **Parameters**, **Request Body**, and **Response Body** — exportable as **Excel** or **CSV**. The tool targets analysts, developers, and QA engineers who need a single, always-current source of truth for API surface areas.

## Overview

* ✅ **OpenAPI 3.x** → tabular summaries ready for CSV/Excel distribution
* ✅ Safe **local `$ref`** resolution with cycle detection and pragmatic combinator handling (`allOf`, `oneOf`, `anyOf`)
* ✅ Rich **constraint extraction** into a compact `Expected Value(s)` string (types, enums, numeric/string/array limits)
* ✅ Built-in **formatting cues** for mandatory fields (bold cells in Excel output)
* ✅ Tested across unit, writer, CLI, and integration layers with CI coverage

Python **3.10 – 3.12** is supported (see [`.github/workflows/tests.yml`](.github/workflows/tests.yml)).

## Documentation

Detailed product requirements and design intent live in the `docs/` directory:

* [`docs/API Description Tool SRS 2 (Updated).md`](docs/API%20Description%20Tool%20SRS%202%20(Updated).md) — software requirements specification (scope, functional rules, non-functional targets).
* [`docs/API Description Tool – Solution Design (Updated).md`](docs/API%20Description%20Tool%20%E2%80%93%20Solution%20Design%20(Updated).md) — component architecture, algorithms, and testing strategy.
* [`docs/CR#1 filtering_190925_8.md`](docs/CR%231%20filtering_190925_8.md) — change-request history.

Referencing these specs ensures feature work stays aligned with the agreed decisions (for example, request/response array asymmetry, validation behaviour, enum handling, and filename precedence).

## Installation

```bash
# clone & enter
git clone https://github.com/<YOUR_GH_USER>/api-description-tool.git
cd api-description-tool

# optional: create venv
python -m venv .venv
source .venv/bin/activate  # Windows: .\.venv\Scripts\Activate.ps1

# install dependencies for development & CLI use
python -m pip install -U pip
python -m pip install -r requirements-dev.txt
python -m pip install -e .
```

## Configuration

The CLI reads INI files that follow the schema implemented in `api_description_tool/config.py`. A minimal `config.ini` might look like:

```ini
[input]
validate = True       ; Toggle `openapi-spec-validator`

[output]
format = xlsx         ; csv | xlsx
file_name = api_tab_desc
```

When `file_name` remains at the default value, the tool derives the final base name from the input YAML stem.

An example configuration is available at [`config_example.ini`](config_example.ini).

## Usage

```bash
python -m api_description_tool.cli <input_file> [output_file] [--config CONFIG]
```

* `input_file` — path to an OpenAPI 3.x YAML document.
* `output_file` (optional) — base name for generated artifacts. For Excel, `.xlsx` is appended; for CSV, three suffixed files are produced.
* `--config` — path to an INI file (default: `config.ini` in the current working directory).

### Filename precedence

1. Positional `output_file` argument (if provided)
2. `config.output.file_name` when it differs from the default `api_tab_desc`
3. `<input_stem>_api_tab_desc` derived from the input filename

### Examples

```bash
# Excel with auto-derived name (e.g. my_api_api_tab_desc.xlsx)
python -m api_description_tool.cli specs/my_api.yaml --config config.ini

# Explicit base name written to CSV trio (outbase_params.csv, ...)
python -m api_description_tool.cli specs/my_api.yaml outbase --config config.ini
```

## Web backend (MVP)

The FastAPI backend introduced in CR-002 can be run locally with Uvicorn:

```bash
uvicorn web.backend.app:app --host 0.0.0.0 --port 8000
```

Visit `http://localhost:8000/health` to confirm the service responds with the current
version and git SHA.

## Output format

### CSV artefacts

* `<base>_params.csv` — `Name | Mandatory | Expected Value(s) | In | Description | Examples`
* `<base>_req_body.csv` — `Path | Property | Mandatory | Expected Value(s) | Description | Examples`
* `<base>_res_body.csv` — `Status | Path | Property | Mandatory | Expected Value(s) | Description | Examples`

### Excel workbook

Single workbook with three sheets: **Params**, **Req Body**, **Res Body** (same columns as CSV). Mandatory rows receive bold emphasis on the relevant headers:

* Params: **Name**
* Req/Res: **Path** and **Property**

The writers always emit header rows, even when a section has zero data rows.

## Constraint extraction

The tables compress schema details into the `Expected Value(s)` column. Examples include:

* `string minLen=2 maxLen=5 pattern=^[A-Z]+$`
* `integer min=1 max=10`
* `array<string> minItems=1`
* `string enum=a,b,c`

Underlying extraction is handled in `api_description_tool/flattener.py` and respects the union/merge behaviour described in the SRS.

## Behaviour notes & limits

* Only **local** `$ref` targets (e.g. `#/components/schemas/...`) are resolved; cycles are detected and short-circuited.
* `allOf` merges properties and `required` entries; `oneOf/anyOf` expose the union of visible properties with a note indicating combinator use.
* Array traversal is asymmetric by design: request tables omit primitive item rows; response tables include them (e.g. `/kinds[0]`).
* Optional OpenAPI validation (using `openapi-spec-validator`) aborts execution on failure.

## How it works

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

Each module has focused responsibilities:

* `cli.py` — orchestrates argument parsing, config loading, validation, and invocation of downstream builders.
* `config.py` — typed loading of INI settings with sensible defaults.
* `parser.py` — consumes OpenAPI YAML and prepares structures for table generation.
* `flattener.py` — resolves `$ref`, merges combinators, and assembles constraint strings.
* `tables.py` — constructs the Params / Req Body / Res Body rows, including the array asymmetry rule.
* `writer_csv.py` & `writer_excel.py` — persist tabular data with consistent formatting and mandatory emphasis.
* `tests/` — pytest suite covering units, writers, CLI behaviour, and integration specs.

## Testing

Run the full suite with:

```bash
python -m pytest
```

Integration fixtures under `tests/data/` ensure the CLI and table generation remain stable against real-world specifications.

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
```

For further context, consult the SRS and solution design documents in `docs/` while making enhancements or reviewing change requests.
