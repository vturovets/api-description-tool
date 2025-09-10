"""
Builds tabular views for Params, Request Body, and Response Body from an OpenAPI 3.x spec.
This version delegates schema flattening & constraints to flattener.py and avoids deep recursion.
"""
from __future__ import annotations

from typing import Dict, Iterable, List, Optional

from .flattener import (
    resolve_ref,
    extract_constraints as _extract_constraints,
    flatten_for_table,
)


# Re-export for tests/backward-compat
extract_constraints = _extract_constraints


def _iter_operations(spec: dict) -> Iterable[tuple]:
    paths = (spec or {}).get("paths", {})
    for url, item in paths.items():
        if not isinstance(item, dict):
            continue
        for method, op in item.items():
            if method.lower() not in {"get", "put", "post", "delete", "options", "head", "patch", "trace"}:
                continue
            yield url, method.lower(), op


def _first_json_schema(content: Optional[dict], components: Optional[dict]) -> Optional[dict]:
    if not isinstance(content, dict):
        return None
    # Prefer application/json; otherwise first available
    candidates = ["application/json", "application/problem+json"] + list(content.keys())
    for mt in candidates:
        media = content.get(mt)
        if not isinstance(media, dict):
            continue
        schema = media.get("schema")
        if not isinstance(schema, dict):
            continue
        # Resolve top-level $ref to avoid shallow wrappers
        return resolve_ref(schema, components, ref_stack=[], ref_cache={}) or schema
    return None


def build_request_params_table(spec: dict, config: Optional[dict] = None) -> List[Dict[str, object]]:
    rows: List[Dict[str, object]] = []
    components = (spec or {}).get("components", {})

    for url, method, op in _iter_operations(spec):
        for p in op.get("parameters", []) or []:
            if not isinstance(p, dict):
                continue
            # Resolve parameter $ref (OpenAPI allows $ref for parameters)
            if "$ref" in p:
                p = resolve_ref(p, components, ref_stack=[], ref_cache={}) or p
            schema = p.get("schema") or {}
            if "$ref" in schema:
                schema = resolve_ref(schema, components, ref_stack=[], ref_cache={}) or schema
            rows.append(
                {
                    "Name": p.get("name", ""),
                    "Mandatory": bool(p.get("required", False)),
                    "Expected Value(s)": extract_constraints(schema),
                    "In": p.get("in", ""),
                    "Description": p.get("description", ""),
                    "Examples": str(p.get("example", "")),
                }
            )
    return rows


def build_request_body_table(spec: dict, config: Optional[dict] = None) -> List[Dict[str, object]]:
    rows: List[Dict[str, object]] = []
    components = (spec or {}).get("components", {})

    for url, method, op in _iter_operations(spec):
        rb = op.get("requestBody")
        if not isinstance(rb, dict):
            continue
        schema = _first_json_schema(rb.get("content"), components)
        if not isinstance(schema, dict):
            continue
        flattened = flatten_for_table(
            schema,
            components=components,
            base_path="",
            emit_array_item_row=False,  # per current tests: don't create rows for primitive array items in request body
        )
        rows.extend(flattened)
    return rows


def build_response_body_table(spec: dict, config: Optional[dict] = None) -> List[Dict[str, object]]:
    rows: List[Dict[str, object]] = []
    components = (spec or {}).get("components", {})

    for url, method, op in _iter_operations(spec):
        responses = op.get("responses", {}) or {}
        for status, r in responses.items():
            if not isinstance(r, dict):
                continue
            schema = _first_json_schema(r.get("content"), components)
            if not isinstance(schema, dict):
                continue
            flattened = flatten_for_table(
                schema,
                components=components,
                base_path="",
                emit_array_item_row=True,  # allow explicit item row for primitive arrays (kinds[0] etc.)
            )
            for row in flattened:
                new_row = dict(row)
                new_row["Status"] = str(status)
                rows.append(new_row)
    return rows