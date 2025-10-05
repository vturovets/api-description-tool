import textwrap
from pathlib import Path

import pytest

from api_description_tool.config import load_config


def test_load_config_missing_file(tmp_path: Path) -> None:
    missing_file = tmp_path / "does_not_exist.ini"

    result = load_config(str(missing_file))

    assert result == {}


def test_load_config_reads_sections(tmp_path: Path) -> None:
    cfg_content = textwrap.dedent(
        """
        [input]
        source = api.yaml

        [output]
        format = csv

        [filtering]
        include = status=public
        """
    ).strip()
    cfg_path = tmp_path / "config.ini"
    cfg_path.write_text(cfg_content, encoding="utf-8")

    result = load_config(str(cfg_path))

    assert result["input"] == {"source": "api.yaml"}
    assert result["output"] == {"format": "csv"}
    assert result["filtering"] == {"include": "status=public"}


def test_load_config_adds_optional_sections(tmp_path: Path) -> None:
    cfg_content = textwrap.dedent(
        """
        [input]
        source = api.yaml
        """
    ).strip()
    cfg_path = tmp_path / "config.ini"
    cfg_path.write_text(cfg_content, encoding="utf-8")

    result = load_config(str(cfg_path))

    assert result["input"] == {"source": "api.yaml"}
    assert result["output"] == {}
    assert result["filtering"] == {}
