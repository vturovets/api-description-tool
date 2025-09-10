import pytest
from api_description_tool.parser import load_yaml, validate_openapi


def test_load_yaml_ok(tmp_path, valid_openapi_spec_dict):
    p = tmp_path / "spec.yaml"
    import yaml
    p.write_text(yaml.safe_dump(valid_openapi_spec_dict), encoding="utf-8")
    data = load_yaml(str(p))
    assert data["openapi"].startswith("3.0")


def test_load_yaml_not_found():
    with pytest.raises(FileNotFoundError):
        load_yaml("missing.yaml")


def test_validate_openapi_valid(valid_openapi_spec_dict):
    assert validate_openapi(valid_openapi_spec_dict) is True


def test_validate_openapi_invalid(invalid_openapi_spec_dict):
    with pytest.raises(ValueError):
        validate_openapi(invalid_openapi_spec_dict)