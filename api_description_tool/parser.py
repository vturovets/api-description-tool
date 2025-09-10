import yaml
from pathlib import Path
from openapi_spec_validator import validate_spec
from openapi_spec_validator.validation.exceptions import (
    OpenAPIValidationError,
    ValidatorDetectError,
)


def load_yaml(file_path: str) -> dict:
    """Load YAML file into Python dict."""
    p = Path(file_path)
    if not p.exists():
        raise FileNotFoundError(f"YAML file not found: {file_path}")
    with p.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def validate_openapi(spec: dict) -> bool:
    """Validate that spec meets OpenAPI 3.x using openapi-spec-validator.
    Raises ValueError if invalid.
    """
    try:
        validate_spec(spec)
        return True
    except (OpenAPIValidationError, ValidatorDetectError) as e:
        # Normalize validator exceptions into ValueError for callers/tests
        raise ValueError(f"OpenAPI validation failed: {e}") from e