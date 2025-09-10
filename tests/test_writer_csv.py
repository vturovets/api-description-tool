import csv
from pathlib import Path

from api_description_tool.writer_csv import write_csv


def test_write_csv_creates_three_files(tmp_path):
    base = tmp_path / "out"
    params = [{"Name": "x", "Mandatory": True, "Expected Value(s)": "string", "In": "header", "Description": "", "Examples": ""}]
    req = [{"Path": "", "Property": "name", "Mandatory": True, "Expected Value(s)": "string", "Description": "", "Examples": ""}]
    res = [{"Status": "200", "Path": "", "Property": "id", "Mandatory": True, "Expected Value(s)": "integer", "Description": "", "Examples": ""}]

    write_csv(str(base), params, req, res)

    for suffix in ("_params.csv", "_req_body.csv", "_res_body.csv"):
        fp = Path(str(base) + suffix)
        assert fp.exists()
        with fp.open(newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            assert rows, f"no rows in {fp}"