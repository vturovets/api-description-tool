import copy
from configparser import ConfigParser

import pytest

from api_description_tool.filter import (
    FilteringError,
    apply_filters,
    load_filter_rules,
)


def make_spec(paths):
    return {
        "openapi": "3.0.0",
        "info": {"title": "Demo", "version": "1.0.0"},
        "paths": copy.deepcopy(paths),
    }


def test_load_filter_rules_from_mapping():
    config = {
        "filtering": {
            "path": " /pets ",
            "method": " get ",
        }
    }

    rules = load_filter_rules(config)

    assert rules == {"path": "/pets", "method": "GET"}


def test_load_filter_rules_unknown_config_type_returns_empty():
    rules = load_filter_rules(object())

    assert rules == {}


def test_apply_filters_requires_dict_spec():
    with pytest.raises(TypeError):
        apply_filters([], {})


def test_apply_filters_no_rules_single_endpoint_returns_copy():
    spec = make_spec({"/pets": {"get": {"operationId": "listPets"}}})

    result = apply_filters(spec, {})

    assert result == spec
    assert result is not spec


def test_apply_filters_no_rules_multiple_endpoints_errors():
    spec = make_spec(
        {
            "/pets": {"get": {}},
            "/orders": {"get": {}},
        }
    )

    with pytest.raises(FilteringError):
        apply_filters(spec, {})


def test_apply_filters_method_without_path_errors():
    spec = make_spec({"/pets": {"get": {}}})

    with pytest.raises(FilteringError):
        apply_filters(spec, {"method": "GET"})


def test_apply_filters_missing_path_errors():
    spec = make_spec(
        {
            "/pets": {"get": {}},
            "/orders": {"get": {}},
        }
    )

    with pytest.raises(FilteringError):
        apply_filters(spec, {"path": ""})


def test_apply_filters_unknown_path_errors():
    spec = make_spec({"/pets": {"get": {}}})

    with pytest.raises(FilteringError):
        apply_filters(spec, {"path": "/orders"})


def test_apply_filters_invalid_path_item_errors():
    spec = make_spec({"/pets": None})

    with pytest.raises(FilteringError):
        apply_filters(spec, {"path": "/pets"})


def test_apply_filters_multiple_methods_without_method_rule_errors():
    spec = make_spec({"/pets": {"get": {}, "post": {}}})

    with pytest.raises(FilteringError):
        apply_filters(spec, {"path": "/pets"})


def test_apply_filters_unknown_method_errors():
    spec = make_spec({"/pets": {"get": {}}})

    with pytest.raises(FilteringError):
        apply_filters(spec, {"path": "/pets", "method": "POST"})


def test_apply_filters_filters_spec_and_preserves_metadata():
    spec = make_spec(
        {
            "/pets": {
                "parameters": ["path-level"],
                "get": {"operationId": "listPets"},
                "post": {"operationId": "createPet"},
            },
            "/orders": {"get": {"operationId": "listOrders"}},
        }
    )

    result = apply_filters(spec, {"path": "/pets", "method": "post"})

    assert set(result.keys()) == {"openapi", "info", "paths"}
    assert result["paths"] == {
        "/pets": {
            "parameters": ["path-level"],
            "post": {"operationId": "createPet"},
        }
    }


def test_apply_filters_infers_method_when_single_choice():
    spec = make_spec({"/pets": {"get": {}}})

    result = apply_filters(spec, {"path": "/pets"})

    assert result["paths"] == {"/pets": {"get": {}}}

