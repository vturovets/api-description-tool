"""
Schema flattener with safe $ref resolution and cycle guards.
Produces normalized rows for request/response body tables.

Exports
-------
- resolve_ref(schema, components, ref_stack=None, ref_cache=None)
- extract_constraints(schema)
- flatten_for_table(schema, components=None, base_path="", emit_array_item_row=False, max_depth=24)
"""
from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Set, Tuple


# -----------------------------
# $ref resolution (cycle-safe)
# -----------------------------

def _lookup_ref(ref: str, components: Optional[dict]) -> Optional[dict]:
    if not components or not ref.startswith("#/"):
        return None
    # Only support local component refs for now: #/components/schemas/Name
    parts = ref.lstrip("#/").split("/")
    node: dict = {"components": components}.get(parts[0]) if parts[0] == "components" else None
    if node is None:
        return None
    for p in parts[1:]:
        if not isinstance(node, dict) or p not in node:
            return None
        node = node[p]
    return node


def resolve_ref(
        schema: dict,
        components: Optional[dict],
        ref_stack: Optional[List[str]] = None,
        ref_cache: Optional[Dict[str, dict]] = None,
) -> dict:
    """Resolve a local $ref. Uses a stack to prevent cycles and a cache for speed.
    Returns the *target schema* (not a deep copy). If cycle detected, returns a benign stub.
    """
    if not isinstance(schema, dict):
        return schema
    if "$ref" not in schema:
        return schema

    ref = schema.get("$ref")
    if ref_cache is None:
        ref_cache = {}
    if ref in ref_cache:
        return ref_cache[ref]

    if ref_stack is None:
        ref_stack = []
    if ref in ref_stack:
        # Cycle detected; produce a stub to break recursion gracefully.
        stub = {"type": "object", "x-circular": ref}
        ref_cache[ref] = stub
        return stub

    target = _lookup_ref(ref, components)
    if target is None:
        # Unresolvable ref -> return as-is to avoid crashing; caller can still inspect $ref
        return schema

    ref_stack.append(ref)
    # Recurse to collapse chains like A -> B -> C
    resolved = resolve_ref(target, components, ref_stack=ref_stack, ref_cache=ref_cache)
    ref_stack.pop()

    ref_cache[ref] = resolved
    return resolved


# -----------------------------
# Constraint extraction
# -----------------------------

def _fmt_num(x):
    try:
        # Avoid trailing .0 for ints passed as float
        return str(int(x)) if isinstance(x, (int,)) or (isinstance(x, float) and x.is_integer()) else str(x)
    except Exception:
        return str(x)


def extract_constraints(schema: Optional[dict]) -> str:
    """Builds a compact constraint string for Expected Value(s).
    Examples: "string", "string enum=a,b", "integer min=1 max=10",
              "string minLen=2 maxLen=5 pattern=^[A-Z]+$", "array<string> minItems=1".
    """
    if not isinstance(schema, dict):
        return ""

    s_type = schema.get("type")
    fmt = schema.get("format")
    pieces: List[str] = []

    # Special-case: enum without type
    if not s_type and "enum" in schema:
        pieces.append("enum=" + ",".join(map(str, schema.get("enum", []))))
        return " ".join(pieces).strip()

    if s_type:
        if s_type == "array":
            items = schema.get("items") or {}
            # Resolve a simple type name for items
            item_t = items.get("type") if isinstance(items, dict) else None
            if not item_t and isinstance(items, dict) and "enum" in items:
                item_t = "enum{" + ",".join(map(str, items.get("enum", []))) + "}"
            inner = item_t or "object"
            pieces.append(f"array<{inner}>")
            if "minItems" in schema:
                pieces.append(f"minItems={_fmt_num(schema['minItems'])}")
            if "maxItems" in schema:
                pieces.append(f"maxItems={_fmt_num(schema['maxItems'])}")
            if schema.get("uniqueItems") is True:
                pieces.append("unique")
        else:
            pieces.append(s_type + (f"({fmt})" if fmt else ""))
            if s_type in {"integer", "number"}:
                if "minimum" in schema:
                    pieces.append(f"min={_fmt_num(schema['minimum'])}")
                if "maximum" in schema:
                    pieces.append(f"max={_fmt_num(schema['maximum'])}")
                if "exclusiveMinimum" in schema:
                    pieces.append(f"exclusiveMin={_fmt_num(schema['exclusiveMinimum'])}")
                if "exclusiveMaximum" in schema:
                    pieces.append(f"exclusiveMax={_fmt_num(schema['exclusiveMaximum'])}")
                if "multipleOf" in schema:
                    pieces.append(f"multipleOf={_fmt_num(schema['multipleOf'])}")
            if s_type == "string":
                if "minLength" in schema:
                    pieces.append(f"minLen={_fmt_num(schema['minLength'])}")
                if "maxLength" in schema:
                    pieces.append(f"maxLen={_fmt_num(schema['maxLength'])}")
                if "pattern" in schema:
                    pieces.append(f"pattern={schema['pattern']}")
            if s_type == "object" and "additionalProperties" in schema:
                ap = schema.get("additionalProperties")

                def _describe_additional_properties(value) -> str:
                    if isinstance(value, bool):
                        return "true" if value else "false"
                    if isinstance(value, dict):
                        ref = value.get("$ref")
                        if isinstance(ref, str) and ref:
                            part = ref.rsplit("/", 1)[-1]
                            return part or ref
                        inner_type = value.get("type")
                        if isinstance(inner_type, str) and inner_type:
                            return inner_type
                        if "enum" in value:
                            return "enum{" + ",".join(map(str, value.get("enum", []))) + "}"
                    return "object"

                pieces.append(f"additionalProperties={_describe_additional_properties(ap)}")
        # Enums apply at any level
        if "enum" in schema and s_type != "array":
            pieces.append("enum=" + ",".join(map(str, schema.get("enum", []))))

    return " ".join(pieces).strip()


# -----------------------------
# Flattening
# -----------------------------

def _examples_from(schema: dict) -> str:
    if not isinstance(schema, dict):
        return ""
    if "example" in schema:
        return str(schema["example"])
    ex = schema.get("examples")
    if isinstance(ex, (list, tuple)) and ex:
        return ", ".join(map(str, ex[:3]))
    if isinstance(ex, dict) and ex:
        # RFC 7807 examples dict form
        return ", ".join(map(lambda k: str(ex[k]) if not isinstance(ex[k], dict) else str(ex[k].get("value")), list(ex)[:3]))
    return ""


def _is_object(schema: dict) -> bool:
    return bool(
        (schema.get("type") == "object")
        or (isinstance(schema.get("properties"), dict) and schema.get("properties"))
        or ("additionalProperties" in schema)
    )


def _iter_object_properties(schema: dict) -> Iterable[Tuple[str, dict, bool, str]]:
    """Yield (prop_name, prop_schema, is_required, prop_description)."""
    required = set(schema.get("required") or [])
    props = schema.get("properties") or {}
    for name, sub in props.items():
        yield name, sub, name in required, str((sub or {}).get("description", ""))


def flatten_for_table(
        schema: Optional[dict],
        components: Optional[dict] = None,
        base_path: str = "",
        *,
        emit_array_item_row: bool = False,
        max_depth: int = 24,
) -> List[Dict[str, object]]:
    """Flatten an OpenAPI/JSON Schema into table rows.

    Returns a list of dicts with keys: Path, Property, Mandatory, Expected Value(s), Description, Examples.

    Rules:
    - Objects: list each property as a row (no row for the object container itself).
    - Arrays:
        * arrays of **primitives**: optionally emit a row at path "<base>/<prop>[0]" with empty Property.
        * arrays of **objects**: descend into the object with path "<base>/<prop>[0]".
    - $ref: resolved safely, with cycles broken via a stub.
    - Depth is capped to avoid pathological recursion.
    """
    if not isinstance(schema, dict):
        return []

    results: List[Dict[str, object]] = []
    ref_cache: Dict[str, dict] = {}

    def walk(
            s: dict,
            path: str,
            *,
            depth: int,
            inherited_array_mandatory: bool,
    ) -> None:
        if depth > max_depth:
            return
        # collapse $ref chains early
        if "$ref" in s:
            s = resolve_ref(s, components, ref_stack=[], ref_cache=ref_cache) or s

        # Handle composed schemas minimally (prefer first viable branch)
        for comb in ("allOf", "oneOf", "anyOf"):
            if comb in s and isinstance(s[comb], list) and s[comb]:
                # try to merge minimal essential bits: properties + required
                merged: dict = {"type": s.get("type")}
                props: dict = {}
                req: List[str] = []
                for part in s[comb]:
                    if "$ref" in part:
                        part = resolve_ref(part, components, ref_stack=[], ref_cache=ref_cache) or part
                    props.update(part.get("properties", {}))
                    if part.get("required"):
                        req.extend(part.get("required"))
                if props:
                    merged["properties"] = props
                if req:
                    merged["required"] = list(dict.fromkeys(req))
                # keep other constraints/types if present
                for k in ("type", "items", "minItems", "maxItems", "enum", "format", "minimum", "maximum", "minLength", "maxLength", "pattern"):
                    if k in s and k not in merged:
                        merged[k] = s[k]
                s = merged
                break

        if _is_object(s):
            for prop, sub, is_req, desc in _iter_object_properties(s):
                # resolve property $ref
                if isinstance(sub, dict) and "$ref" in sub:
                    sub = resolve_ref(sub, components, ref_stack=[], ref_cache=ref_cache) or sub

                row_mandatory = bool(is_req) or inherited_array_mandatory
                # primitives -> row
                if isinstance(sub, dict) and sub.get("type") in {"string", "integer", "number", "boolean", "null"} or (
                        isinstance(sub, dict) and "enum" in sub and sub.get("type") != "array"
                ):
                    results.append(
                        {
                            "Path": path,
                            "Property": prop,
                            "Mandatory": row_mandatory,
                            "Expected Value(s)": extract_constraints(sub),
                            "Description": desc,
                            "Examples": _examples_from(sub),
                        }
                    )
                elif isinstance(sub, dict) and sub.get("type") == "array":
                    items = sub.get("items") or {}
                    array_mandatory = row_mandatory or (isinstance(sub, dict) and sub.get("minItems", 0) > 0)
                    # row for primitives-in-array (optional)
                    if emit_array_item_row and isinstance(items, dict) and (
                            items.get("type") in {"string", "integer", "number", "boolean", "null"} or "enum" in items
                    ):
                        results.append(
                            {
                                "Path": f"{path}/{prop}[0]" if path else f"/{prop}[0]",
                                "Property": "",
                                "Mandatory": array_mandatory,
                                "Expected Value(s)": extract_constraints(items),
                                "Description": desc,
                                "Examples": _examples_from(items) or _examples_from(sub),
                            }
                        )
                    # descend into object items
                    next_path = f"{path}/{prop}[0]" if path else f"/{prop}[0]"
                    if isinstance(items, dict):
                        if "$ref" in items:
                            items = resolve_ref(items, components, ref_stack=[], ref_cache=ref_cache) or items
                        if isinstance(items, dict) and (
                                _is_object(items) or items.get("type") == "array"
                        ):
                            walk(
                                items,
                                next_path,
                                depth=depth + 1,
                                inherited_array_mandatory=array_mandatory,
                            )
                else:
                    # object-ish (no primitive type), descend
                    next_path = f"{path}/{prop}" if path else f"/{prop}"
                    if isinstance(sub, dict):
                        walk(
                            sub,
                            next_path,
                            depth=depth + 1,
                            inherited_array_mandatory=inherited_array_mandatory,
                        )
        elif s.get("type") == "array":
            items = s.get("items") or {}
            item_path = f"{path}[0]" if path else "/[0]"
            array_mandatory = inherited_array_mandatory or (isinstance(s, dict) and s.get("minItems", 0) > 0)
            if emit_array_item_row and isinstance(items, dict) and (
                    items.get("type") in {"string", "integer", "number", "boolean", "null"} or "enum" in items
            ):
                results.append(
                    {
                        "Path": item_path,
                        "Property": "",
                        "Mandatory": array_mandatory,
                        "Expected Value(s)": extract_constraints(items),
                        "Description": str(s.get("description", "")),
                        "Examples": _examples_from(items) or _examples_from(s),
                    }
                )
            if isinstance(items, dict):
                if "$ref" in items:
                    items = resolve_ref(items, components, ref_stack=[], ref_cache=ref_cache) or items
                if isinstance(items, dict) and (
                        _is_object(items) or items.get("type") == "array"
                ):
                    walk(
                        items,
                        item_path,
                        depth=depth + 1,
                        inherited_array_mandatory=array_mandatory,
                    )
        else:
            # primitive at root -> single row
            results.append(
                {
                    "Path": path,
                    "Property": "",
                    "Mandatory": False,
                    "Expected Value(s)": extract_constraints(s),
                    "Description": str(s.get("description", "")),
                    "Examples": _examples_from(s),
                }
            )

    walk(schema, base_path, depth=0, inherited_array_mandatory=False)
    return results
