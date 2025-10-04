# api_description_tool/config.py
from configparser import ConfigParser
from pathlib import Path
from typing import Dict


def load_config(path: str) -> Dict[str, Dict[str, str]]:
    """
    Load config from an INI file. Returns a nested dict with known sections.
    If the file doesn't exist, returns an empty dict (tool has sensible defaults).
    """
    cfg_path = Path(path)
    if not cfg_path.exists():
        return {}

    parser = ConfigParser()
    parser.read(cfg_path, encoding="utf-8")

    out: Dict[str, Dict[str, str]] = {}

    for section in parser.sections():
        out[section] = {}
        for k, v in parser.items(section):
            out[section][k] = v

    # Ensure sections exist even if missing (optional)
    out.setdefault("input", {})
    out.setdefault("output", {})
    # 'filtering' is optional and only used by CR-001
    if "filtering" not in out:
        out["filtering"] = {}

    return out
