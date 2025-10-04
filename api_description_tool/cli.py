# api_description_tool/cli.py
from pathlib import Path
import argparse
import sys

from api_description_tool.config import load_config
from api_description_tool.parser import load_yaml, validate_openapi
from api_description_tool.tables import (
    build_request_params_table,
    build_request_body_table,
    build_response_body_table,
)
from api_description_tool.writer_excel import write_excel
from api_description_tool.writer_csv import write_csv

# CR-001 filtering
from api_description_tool.filter import load_filter_rules, apply_filters, FilteringError


def _to_bool(val, default=True):
    """Parse True/False from various string/bool inputs."""
    if isinstance(val, bool):
        return val
    if val is None:
        return default
    s = str(val).strip().lower()
    if s in {"1", "true", "t", "yes", "y", "on"}:
        return True
    if s in {"0", "false", "f", "no", "n", "off"}:
        return False
    return default


def _ensure_min_rows(rows, kind):
    """
    Ensure writers always have at least headers to emit.
    Returns the original list if non-empty; otherwise, a single empty row
    with the expected columns for the given table kind.
    """
    if rows:
        return rows

    if kind == "params":
        # Name | Mandatory | Expected Value(s) | In | Description | Examples
        return [
            {
                "Name": "",
                "Mandatory": "",
                "Expected Value(s)": "",
                "In": "",
                "Description": "",
                "Examples": "",
            }
        ]
    elif kind == "req":
        # Path | Property | Mandatory | Expected Value(s) | Description | Examples
        return [
            {
                "Path": "",
                "Property": "",
                "Mandatory": "",
                "Expected Value(s)": "",
                "Description": "",
                "Examples": "",
            }
        ]
    elif kind == "res":
        # Status | Path | Property | Mandatory | Expected Value(s) | Description | Examples
        return [
            {
                "Status": "",
                "Path": "",
                "Property": "",
                "Mandatory": "",
                "Expected Value(s)": "",
                "Description": "",
                "Examples": "",
            }
        ]
    else:
        return [{}]


def main():
    parser = argparse.ArgumentParser(
        description="API Description Tool - Convert OpenAPI 3.x YAML to tables"
    )
    parser.add_argument("input_file", help="Path to OpenAPI YAML file")
    parser.add_argument("output_file", nargs="?", help="Optional output base/file")
    parser.add_argument("--config", default="config.ini", help="Path to config file")
    args = parser.parse_args()

    try:
        # --- Config ---
        cfg = load_config(args.config)  # returns a dict with sections or {}

        out_section = cfg.get("output", {}) if isinstance(cfg, dict) else {}
        in_section = cfg.get("input", {}) if isinstance(cfg, dict) else {}

        validate_flag = _to_bool(in_section.get("validate", "True"), default=True)
        fmt = (out_section.get("format") or "xlsx").strip().lower()

        input_path = Path(args.input_file)

        # default base name: <input_stem>_api_tab_desc
        default_base = f"{input_path.stem}_api_tab_desc"
        cfg_base = (out_section.get("file_name") or "").strip()

        if args.output_file:
            base_name = args.output_file
        elif cfg_base and cfg_base.lower() != "api_tab_desc":
            base_name = cfg_base
        else:
            base_name = default_base

        print(f"Input file: {input_path}")
        print(f"Resolved output base: {Path(base_name).resolve()}")
        print(f"Selected format: {fmt}")
        print(f"Validation enabled: {validate_flag}")

        # --- Load YAML ---
        spec = load_yaml(args.input_file)

        # --- CR-001: filtering (after YAML load, before parsing/tables) ---
        try:
            rules = load_filter_rules(cfg)  # accepts dict-style config
            spec = apply_filters(spec, rules)
        except FilteringError as e:
            print(f"[Filtering] {e}")
            sys.exit(1)

        # --- (Optional) Validate OpenAPI ---
        if validate_flag:
            validate_openapi(spec)

        # --- Build tables ---
        params = build_request_params_table(spec, cfg)
        req_body = build_request_body_table(spec, cfg)
        res_body = build_response_body_table(spec, cfg)

        # Ensure we always produce files
        params = _ensure_min_rows(params, "params")
        req_body = _ensure_min_rows(req_body, "req")
        res = _ensure_min_rows(res_body, "res")
        if res_body and all("Status" in r for r in res_body):
            res = res_body

        print(f"Parameter table rows: {len(params)}")
        print(f"Request body table rows: {len(req_body)}")
        print(f"Response body table rows: {len(res)}")

        # --- Write output ---
        if fmt in {"xlsx", "excel"}:
            out_path = base_name + ".xlsx"
            write_excel(out_path, params, req_body, res)
            print(f"✅ Wrote Excel file: {out_path}")
        elif fmt == "csv":
            write_csv(base_name, params, req_body, res)
            print(f"✅ Wrote CSV files with base: {base_name}")
        else:
            raise ValueError(f"Unsupported output format: {fmt}")

    except (FileNotFoundError, ValueError) as e:
        print(f"[Error] {e}")
        sys.exit(1)
    except Exception as e:
        print(f"[Error] {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()