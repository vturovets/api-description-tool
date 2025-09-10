# api_description_tool/config.py
import configparser
from pathlib import Path

def get_bool(value: str) -> bool:
    return str(value).lower() in ("1", "true", "yes", "on")

def load_config(config_path: str) -> dict:
    import configparser
    from pathlib import Path

    config = configparser.ConfigParser()
    if not Path(config_path).exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    config.read(config_path, encoding="utf-8")
    settings = {section: dict(config.items(section)) for section in config.sections()}
    return settings
