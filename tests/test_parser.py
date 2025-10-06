import pytest
import yaml
from openapi_spec_validator.validation.exceptions import (
    OpenAPIValidationError,
    ValidatorDetectError,
)

from api_description_tool import parser


def test_load_yaml_returns_dict(tmp_path, valid_openapi_spec_dict):
    spec_path = tmp_path / "spec.yaml"
    spec_path.write_text(yaml.safe_dump(valid_openapi_spec_dict), encoding="utf-8")

    loaded = parser.load_yaml(str(spec_path))

    assert loaded == valid_openapi_spec_dict


def test_load_yaml_missing_file():
    with pytest.raises(FileNotFoundError):
        parser.load_yaml("missing.yaml")


def test_load_yaml_invalid_yaml(tmp_path):
    spec_path = tmp_path / "spec.yaml"
    spec_path.write_text("foo: [\n", encoding="utf-8")

    with pytest.raises(yaml.YAMLError):
        parser.load_yaml(str(spec_path))


def test_validate_openapi_success(valid_openapi_spec_dict):
    assert parser.validate_openapi(valid_openapi_spec_dict) is True


@pytest.mark.parametrize(
    "exception_cls",
    [OpenAPIValidationError, ValidatorDetectError],
)
def test_validate_openapi_wraps_validator_errors(monkeypatch, exception_cls):
    def fake_validate(_spec):
        raise exception_cls("boom")

    monkeypatch.setattr(parser, "validate_spec", fake_validate)

    with pytest.raises(ValueError, match="boom") as exc:
        parser.validate_openapi({"openapi": "3.0.0"})

    assert "OpenAPI validation failed" in str(exc.value)
