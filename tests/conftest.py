import io
import json
import textwrap
from pathlib import Path


import pytest
import yaml

@pytest.fixture
def valid_openapi_spec_dict():
    """A minimal valid OpenAPI 3.0.1 dict that exercises params, req body, $ref, arrays, and 2xx/default responses."""
    return {
        "openapi": "3.0.1",
        "info": {"title": "Sample", "version": "1.0.0"},
        "paths": {
            "/pets": {
                "get": {
                    "parameters": [
                        {
                            "name": "x-correlation-id",
                            "in": "header",
                            "required": True,
                            "schema": {"type": "string"},
                            "description": "Correlation id",
                            "example": "abc-123",
                        }
                    ],
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/PetRequest"}
                            }
                        },
                    },
                    "responses": {
                        "200": {
                            "description": "ok",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/PetResponse"}
                                }
                            },
                        },
                        "default": {
                            "description": "fallback",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "message": {"type": "string", "description": "msg"}
                                        },
                                    }
                                }
                            },
                        },
                    },
                }
            }
        },
        "components": {
            "schemas": {
                "PetRequest": {
                    "type": "object",
                    "required": ["name"],
                    "properties": {
                        "name": {
                            "type": "string",
                            "minLength": 2,
                            "pattern": "^[A-Za-z]+$",
                            "description": "pet name",
                            "example": "Rex",
                        },
                        "tags": {
                            "type": "array",
                            "items": {"type": "string", "enum": ["cute", "fluffy"]},
                        },
                        "owner": {
                            "type": "object",
                            "required": ["first"],
                            "properties": {
                                "first": {"type": "string"},
                                "last": {"type": "string"},
                            },
                        },
                    },
                },
                "PetResponse": {
                    "type": "object",
                    "required": ["id", "name"],
                    "properties": {
                        "id": {"type": "integer", "minimum": 1},
                        "name": {"type": "string", "pattern": "^[A-Za-z]+$"},
                        "owner": {
                            "type": "object",
                            "properties": {
                                "first": {"type": "string"},
                                "last": {"type": "string"},
                            },
                        },
                        "kinds": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                },
            }
        },
    }

@pytest.fixture
def invalid_openapi_spec_dict():
    """Intentionally invalid (missing top-level 'openapi'). Still includes a single
    path to keep CLI running when validation is skipped."""
    return {
        "info": {"title": "bad", "version": "0"},
        "paths": {
            "/health": {
                "get": {"responses": {"200": {"description": "ok"}}}
            }
        },
    }


@pytest.fixture
def write_yaml(tmp_path):
    def _write(obj, name="spec.yaml"):
        p = tmp_path / name
        with p.open("w", encoding="utf-8") as f:
            yaml.safe_dump(obj, f, sort_keys=False)
        return p
    return _write


@pytest.fixture
def make_config(tmp_path):
    def _make(**overrides):
        # Defaults mirroring SRS/Design
        content = {
            "input": {"validate": "True"},
            "output": {"format": "csv", "file_name": "api_tab_desc"},
        }
        # simple INI writer
        lines = []
        for section, kv in content.items():
            lines.append(f"[{section}]")
            for k, v in {**kv, **overrides.get(section, {})}.items():
                lines.append(f"{k}={v}")
        cfg = tmp_path / "config.ini"
        cfg.write_text("\n".join(lines), encoding="utf-8")
        return cfg
    return _make