import pytest
from api_description_tool.config import load_config


def test_load_config_success(tmp_path):
    cfg = tmp_path / "config.ini"
    cfg.write_text("""
[input]
validate=True
[output]
format=csv
file_name=out
""".strip(), encoding="utf-8")
    settings = load_config(str(cfg))
    assert settings["input"]["validate"].lower() == "true"
    assert settings["output"]["format"] == "csv"
    assert settings["output"]["file_name"] == "out"


def test_load_config_missing_file():
    with pytest.raises(FileNotFoundError):
        load_config("nope.ini")