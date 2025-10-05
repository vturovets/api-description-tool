import configparser
import subprocess
import sys
from pathlib import Path

import openpyxl
import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "tests" / "data"
INPUT_SPEC = DATA_DIR / "NGS_ASC-an.yaml"


def _write_config(tmp_path: Path, path_filter: str, output_base: Path) -> Path:
    config = configparser.ConfigParser()
    config.read(REPO_ROOT / "config_example.ini")

    if "filtering" not in config:
        config.add_section("filtering")
    config["filtering"]["path"] = path_filter

    if "output" not in config:
        config.add_section("output")
    config["output"]["file_name"] = str(output_base)

    config_path = tmp_path / "config.ini"
    with config_path.open("w") as fh:
        config.write(fh)
    return config_path


def _run_cli(config_path: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "api_description_tool.cli",
            str(INPUT_SPEC),
            "--config",
            str(config_path),
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )


def _workbook_contents(path: Path) -> dict[str, list[list[object]]]:
    workbook = openpyxl.load_workbook(path)
    try:
        contents: dict[str, list[list[object]]] = {}
        for sheet_name in workbook.sheetnames:
            worksheet = workbook[sheet_name]
            contents[sheet_name] = [
                list(row)
                for row in worksheet.iter_rows(values_only=True)
            ]
        return contents
    finally:
        workbook.close()


@pytest.mark.parametrize(
    "path_filter, expected_filename",
    [
        (
            "/v1/packages/availability/departures",
            "ngs_asc_airports.xlsx",
        ),
        (
            "/v1/packages/availability/countries",
            "ngs_asc_countries.xlsx",
        ),
    ],
)
def test_integration_generates_expected_workbook(tmp_path, path_filter, expected_filename):
    output_base = tmp_path / Path(path_filter).name
    config_path = _write_config(tmp_path, path_filter, output_base)

    result = _run_cli(config_path)
    assert result.returncode == 0, result.stderr

    generated_file = output_base.with_suffix(".xlsx")
    assert generated_file.exists(), "Expected the CLI to create an Excel file"

    expected_file = DATA_DIR / expected_filename
    assert expected_file.exists(), "Expected reference workbook is missing"

    generated_contents = _workbook_contents(generated_file)
    expected_contents = _workbook_contents(expected_file)

    assert generated_contents == expected_contents
