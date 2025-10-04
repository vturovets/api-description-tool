import sys
import builtins
import importlib
import contextlib

import pytest


def run_cli(monkeypatch, argv):
    # import inside to ensure fresh argv each call
    monkeypatch.setenv("PYTHONIOENCODING", "utf-8")
    monkeypatch.setenv("PYTHONUNBUFFERED", "1")
    monkeypatch.setattr(sys, "argv", argv)
    # Re-import module to reset argparse state across tests
    cli = importlib.import_module("api_description_tool.cli")
    importlib.reload(cli)
    return cli


def test_cli_csv_happy_path(
    tmp_path,
    valid_openapi_spec_dict,
    write_yaml,
    make_config,
    monkeypatch,
    capsys,
):
    cfg = make_config(output={"format": "csv", "file_name": "fromcfg"})
    spec_path = write_yaml(valid_openapi_spec_dict)

    monkeypatch.chdir(tmp_path)
    cli = run_cli(monkeypatch, ["prog", str(spec_path), "out", "--config", str(cfg)])

    # Run main()
    cli.main()

    # Expect 3 csv files with explicit base name
    for suffix in ("_params.csv", "_req_body.csv", "_res_body.csv"):
        assert (tmp_path / ("out" + suffix)).exists()

    out = capsys.readouterr().out
    expected_base = (tmp_path / "out").resolve()
    assert f"Input file: {spec_path}" in out
    assert f"Resolved output base: {expected_base}" in out
    assert "Selected format: csv" in out
    assert "Validation enabled: True" in out
    assert "Parameter table rows: 1" in out
    assert "Request body table rows: 3" in out
    assert "Response body table rows: 6" in out


def test_cli_skip_validation_and_still_run(
    tmp_path, invalid_openapi_spec_dict, write_yaml, make_config, monkeypatch, capsys
):
    cfg = make_config(input={"validate": "False"}, output={"format": "csv", "file_name": "skipped"})
    spec_path = write_yaml(invalid_openapi_spec_dict)

    monkeypatch.chdir(tmp_path)
    cli = run_cli(monkeypatch, ["prog", str(spec_path), "--config", str(cfg)])

    cli.main()

    # output base derives from config.file_name when no positional output argument supplied
    for suffix in ("_params.csv", "_req_body.csv", "_res_body.csv"):
        assert (tmp_path / ("skipped" + suffix)).exists()

    out = capsys.readouterr().out
    expected_base = (tmp_path / "skipped").resolve()
    assert f"Input file: {spec_path}" in out
    assert f"Resolved output base: {expected_base}" in out
    assert "Selected format: csv" in out
    assert "Validation enabled: False" in out
    assert "Parameter table rows: 1" in out
    assert "Request body table rows: 1" in out
    assert "Response body table rows: 1" in out


def test_cli_missing_yaml_exits_with_error(tmp_path, make_config, monkeypatch):
    cfg = make_config()
    monkeypatch.chdir(tmp_path)
    cli = run_cli(monkeypatch, ["prog", "does-not-exist.yaml", "--config", str(cfg)])

    with pytest.raises(SystemExit) as ei:
        cli.main()
    assert ei.value.code == 1