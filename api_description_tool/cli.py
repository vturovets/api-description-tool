import argparse
import sys
from pathlib import Path

from .config import load_config
from .parser import load_yaml, validate_openapi
from .tables import (
    build_request_params_table,
    build_request_body_table,
    build_response_body_table,
)
from .writer_csv import write_csv
from .writer_excel import write_excel

_TRUE = {"1", "true", "yes", "on"}


def _to_bool(v, default=True):
    if v is None:
        return default
    return str(v).strip().lower() in _TRUE


def _ensure_min_rows(rows, kind: str):
    if rows:
        return rows
    if kind == "params":
        return [{"Name": "", "Mandatory": False, "Expected Value(s)": "", "In": "", "Description": "", "Examples": ""}]
    if kind == "req":
        return [{"Path": "", "Property": "", "Mandatory": False, "Expected Value(s)": "", "Description": "", "Examples": ""}]
    return [{"Status": "", "Path": "", "Property": "", "Mandatory": False, "Expected Value(s)": "", "Description": "", "Examples": ""}]


def main():
    parser = argparse.ArgumentParser(description="API Description Tool - Convert OpenAPI 3.x YAML to tables")
    parser.add_argument("input_file", help="Path to OpenAPI YAML file")
    parser.add_argument("output_file", nargs="?", help="Optional output base/file")
    parser.add_argument("--config", default="config.ini", help="Path to config file")
    args = parser.parse_args()

    try:
        print("Parsing config…")
        cfg = load_config(args.config)

        out_section = cfg.get("output", {}) if isinstance(cfg, dict) else {}
        in_section = cfg.get("input", {}) if isinstance(cfg, dict) else {}

        validate_flag = _to_bool(in_section.get("validate", "True"), default=True)
        fmt = (out_section.get("format") or "csv").strip().lower()

        # Default base name: <input_stem>_api_tab_desc
        # Precedence: positional output_file > non-default config.file_name > derived from input
        default_base = f"{Path(args.input_file).stem}_api_tab_desc"
        cfg_base = (out_section.get("file_name") or "").strip()
        if args.output_file:
            base_name = args.output_file
        elif cfg_base and cfg_base.lower() != "api_tab_desc":
            base_name = cfg_base
        else:
            base_name = default_base

        print("Loading YAML…")
        spec = load_yaml(args.input_file)

        if validate_flag:
            print("Validating OpenAPI spec…")
            validate_openapi(spec)
        else:
            print("Skipping validation as per config…")

        print("Building tables…")
        params = build_request_params_table(spec, cfg)
        req_body = build_request_body_table(spec, cfg)
        res_body = build_response_body_table(spec, cfg)

        # Ensure writers always create files
        params = _ensure_min_rows(params, "params")
        req_body = _ensure_min_rows(req_body, "req")
        res = _ensure_min_rows(res_body, "res")
        if res_body and all("Status" in r for r in res_body):
            res = res_body

        if fmt in {"xlsx", "excel"}:
            write_excel(base_name + ".xlsx", params, req_body, res)
            print(f"✅ Wrote Excel file: {base_name}.xlsx")
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