
import pytest
from configparser import ConfigParser
from api_description_tool.filter import load_filter_rules, apply_filters, FilteringError

MIN_SPEC = {
    "openapi": "3.0.3",
    "info": {"title": "x", "version": "1.0.0"},
    "paths": {
        "/only": {
            "get": {"responses": {"200": {"description": "ok"}}}
        }
    }
}

MULTI_SPEC = {
    "openapi": "3.0.3",
    "info": {"title": "x", "version": "1.0.0"},
    "paths": {
        "/p1": {
            "get": {"responses": {"200": {"description": "ok"}}},
            "post": {"responses": {"201": {"description": "created"}}},
            "parameters": [{"name": "X", "in": "header"}]
        },
        "/p2": {
            "get": {"responses": {"200": {"description": "ok"}}}
        }
    }
}

def make_config(section_data=None):
    cfg = ConfigParser()
    if section_data is not None:
        cfg.add_section("filtering")
        for k, v in section_data.items():
            cfg.set("filtering", k, v)
    return cfg

def test_load_filter_rules_absent_section():
    cfg = make_config(None)
    assert load_filter_rules(cfg) == {}

def test_load_filter_rules_present_keys():
    cfg = make_config({"path": "/p1", "method": "get"})
    rules = load_filter_rules(cfg)
    assert rules["path"] == "/p1"
    assert rules["method"] == "GET"

def test_apply_no_rules_single_path_single_method_ok():
    out = apply_filters(MIN_SPEC, {})
    assert out["paths"].keys() == {"/only"}

def test_apply_no_rules_multi_endpoints_raises():
    with pytest.raises(FilteringError) as ei:
        apply_filters(MULTI_SPEC, {})
    assert "multiple endpoints" in str(ei.value).lower()

def test_apply_method_alone_forbidden():
    with pytest.raises(FilteringError):
        apply_filters(MULTI_SPEC, {"method": "GET"})

def test_apply_path_missing_in_spec():
    with pytest.raises(FilteringError):
        apply_filters(MULTI_SPEC, {"path": "/missing"})

def test_apply_path_with_multiple_methods_requires_method():
    with pytest.raises(FilteringError):
        apply_filters(MULTI_SPEC, {"path": "/p1"})

def test_apply_path_and_method_selects_only_that_operation():
    out = apply_filters(MULTI_SPEC, {"path": "/p1", "method": "POST"})
    assert list(out["paths"].keys()) == ["/p1"]
    p1 = out["paths"]["/p1"]
    assert "post" in p1 and "get" not in p1  # only POST kept
    # path-level parameters preserved
    assert "parameters" in p1
