import importlib
import sys

import pytest


def load_cli(monkeypatch, argv):
    """Reload the CLI module with a controlled argv/environment."""

    monkeypatch.setenv("PYTHONIOENCODING", "utf-8")
    monkeypatch.setenv("PYTHONUNBUFFERED", "1")
    monkeypatch.setattr(sys, "argv", argv)

    # Ensure a pristine module state across tests
    sys.modules.pop("api_description_tool.cli", None)
    cli = importlib.import_module("api_description_tool.cli")
    return importlib.reload(cli)


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
    cli = load_cli(monkeypatch, ["prog", str(spec_path), "out", "--config", str(cfg)])

    cli.main()

    # Expected CSV artefacts
    for suffix in ("_params.csv", "_req_body.csv", "_res_body.csv"):
        assert (tmp_path / f"out{suffix}").exists()

    out = capsys.readouterr().out
    expected_base = (tmp_path / "out").resolve()
    assert f"Input file: {spec_path}" in out
    assert f"Resolved output base: {expected_base}" in out
    assert "Selected format: csv" in out
    assert "Validation enabled: True" in out
    assert "Parameter table rows: 1" in out
    assert "Request body table rows: 5" in out
    assert "Response body table rows: 8" in out


def test_cli_excel_writer_receives_minimum_rows(
    tmp_path,
    valid_openapi_spec_dict,
    write_yaml,
    make_config,
    monkeypatch,
    capsys,
):
    cfg = make_config(output={"format": "xlsx", "file_name": "excel_out"})
    spec_path = write_yaml(valid_openapi_spec_dict)

    monkeypatch.chdir(tmp_path)
    cli = load_cli(monkeypatch, ["prog", str(spec_path), "--config", str(cfg)])

    monkeypatch.setattr(cli, "build_request_params_table", lambda spec, cfg: [])
    monkeypatch.setattr(cli, "build_request_body_table", lambda spec, cfg: [])
    monkeypatch.setattr(cli, "build_response_body_table", lambda spec, cfg: [])

    recorded = {}

    def fake_write_excel(out_path, params, req_body, res):
        recorded["out_path"] = out_path
        recorded["params"] = params
        recorded["req_body"] = req_body
        recorded["res"] = res

    monkeypatch.setattr(cli, "write_excel", fake_write_excel)

    cli.main()

    assert recorded["out_path"].endswith(".xlsx")
    assert len(recorded["params"]) == 1
    assert len(recorded["req_body"]) == 1
    assert len(recorded["res"]) == 1

    out = capsys.readouterr().out
    assert "✅ Wrote Excel file:" in out


def test_cli_filtering_error_exits_with_message(
    tmp_path,
    valid_openapi_spec_dict,
    write_yaml,
    make_config,
    monkeypatch,
    capsys,
):
    cfg = make_config(output={"format": "csv"})
    spec_path = write_yaml(valid_openapi_spec_dict)

    monkeypatch.chdir(tmp_path)
    cli = load_cli(monkeypatch, ["prog", str(spec_path), "--config", str(cfg)])

    monkeypatch.setattr(cli, "load_filter_rules", lambda cfg: {"rules": []})

    def fail_filters(spec, rules):
        raise cli.FilteringError("boom")

    monkeypatch.setattr(cli, "apply_filters", fail_filters)

    with pytest.raises(SystemExit) as excinfo:
        cli.main()

    assert excinfo.value.code == 1
    out = capsys.readouterr().out
    assert "[Filtering] boom" in out


def test_cli_calls_validation_when_enabled(
    tmp_path,
    valid_openapi_spec_dict,
    write_yaml,
    make_config,
    monkeypatch,
):
    cfg = make_config(output={"format": "csv", "file_name": "val"})
    spec_path = write_yaml(valid_openapi_spec_dict)

    monkeypatch.chdir(tmp_path)
    cli = load_cli(monkeypatch, ["prog", str(spec_path), "--config", str(cfg)])

    called = {"validate": False, "write": False}

    def record_validate(spec):
        called["validate"] = True

    def fake_write_csv(base, params, req_body, res):
        called["write"] = True

    monkeypatch.setattr(cli, "validate_openapi", record_validate)
    monkeypatch.setattr(cli, "write_csv", fake_write_csv)
    monkeypatch.setattr(cli, "build_request_params_table", lambda spec, cfg: [{"Name": "n"}])
    monkeypatch.setattr(cli, "build_request_body_table", lambda spec, cfg: [{"Path": "p"}])
    monkeypatch.setattr(cli, "build_response_body_table", lambda spec, cfg: [{"Status": "200"}])

    cli.main()

    assert called["validate"] is True
    assert called["write"] is True


def test_cli_unsupported_format_prints_error_and_exits(
    tmp_path,
    valid_openapi_spec_dict,
    write_yaml,
    make_config,
    monkeypatch,
    capsys,
):
    cfg = make_config(output={"format": "pdf"})
    spec_path = write_yaml(valid_openapi_spec_dict)

    monkeypatch.chdir(tmp_path)
    cli = load_cli(monkeypatch, ["prog", str(spec_path), "--config", str(cfg)])

    with pytest.raises(SystemExit) as excinfo:
        cli.main()

    assert excinfo.value.code == 1
    out = capsys.readouterr().out
    assert "Unsupported output format" in out
