
"""
CR-001: Endpoint Filtering
-------------------------
Exposes two functions:
  - load_filter_rules(config): read [filtering] from a ConfigParser
  - apply_filters(spec, rules): return a pruned OpenAPI dict according to rules

This module is intentionally self-contained and has no external deps.
It does not mutate the incoming `spec` dict.
"""
from copy import deepcopy
from configparser import ConfigParser
from typing import Dict, Optional, Tuple

from typing import Dict, Optional, Tuple, Mapping
from configparser import ConfigParser

HTTP_METHODS = {"get","put","post","delete","options","head","patch","trace"}

class FilteringError(ValueError):
    """Raised for FR-003..FR-007 style validation errors."""

def load_filter_rules(config) -> Dict[str, Optional[str]]:
    """
    Read [filtering] from either:
      - a dict produced by load_config() in this repo, or
      - a ConfigParser (future-proof).
    Returns {} if the section is missing/empty.
    """
    rules: Dict[str, Optional[str]] = {}

    # Case A: dict-style config (current repo behavior)
    if isinstance(config, Mapping):
        section = config.get("filtering") or {}
        path = (section.get("path") or "").strip()
        method = (section.get("method") or "").strip()
        if path:
            rules["path"] = path  # strict exact match
        if method:
            rules["method"] = method.upper()
        return rules

    # Case B: ConfigParser
    if isinstance(config, ConfigParser):
        if not config.has_section("filtering"):
            return {}
        path = config.get("filtering", "path", fallback="").strip()
        method = config.get("filtering", "method", fallback="").strip()
        if path:
            rules["path"] = path
        if method:
            rules["method"] = method.upper()
        return rules

    # Fallback: unknown type -> treat as no rules
    return {}

def _count_paths_and_methods(spec: Dict) -> Tuple[int, int]:
    paths = spec.get("paths") or {}
    total_paths = len(paths)
    total_methods = 0
    for _, node in paths.items():
        if isinstance(node, dict):
            total_methods += sum(1 for k in node.keys() if k.lower() in HTTP_METHODS)
    return total_paths, total_methods

def apply_filters(spec: Dict, rules: Dict[str, Optional[str]]):
    """Apply CR-001 filtering rules to an OpenAPI 3.x dict.

    FR-002: If no rules and the spec has exactly one path and one method -> return spec unchanged.
    FR-003: If no rules and spec has >1 path or (1 path with >1 method) -> error.
    FR-004..FR-007: Validation around path/method presence/consistency.
    """
    if not isinstance(spec, dict):
        raise TypeError("apply_filters expects an OpenAPI spec dict")

    spec_copy = deepcopy(spec)
    paths = (spec_copy.get("paths") or {})
    rules = rules or {}

    # Normalize method if present
    if "method" in rules and rules["method"]:
        rules["method"] = rules["method"].upper()

    # Case A: No [filtering] provided
    if not rules:
        total_paths, total_methods = _count_paths_and_methods(spec_copy)
        if total_paths == 1 and total_methods == 1:
            return spec_copy  # FR-002 passthrough
        raise FilteringError(
            "Your spec contains multiple endpoints but no filtering rules. "
            "Add [filtering] with path= and method= in config.ini."
        )  # FR-003

    # FR-007: method cannot be specified alone
    path = rules.get("path")
    method = rules.get("method")
    if (not path) and method:
        raise FilteringError(
            "The method cannot be specified alone. Please specify both path and method."
        )

    # With path provided, validate its existence
    if not path:
        # If neither path nor method -> treat as no rules (already handled above), but we re-check to be safe
        total_paths, total_methods = _count_paths_and_methods(spec_copy)
        if total_paths == 1 and total_methods == 1:
            return spec_copy
        raise FilteringError(
            "Your spec contains multiple endpoints but the [filtering] path is missing. "
            "Add [filtering] with path= and method= in config.ini."
        )

    if path not in paths:
        raise FilteringError(
            "Your spec does not contain the required path. "
            "Specify the correct path in the [filtering] section of config.ini with path="
        )  # FR-005

    path_item = paths[path]
    if not isinstance(path_item, dict):
        raise FilteringError(
            "The selected path exists but is not a valid OpenAPI Path Item object."
        )

    # Compute available methods under this path
    available_methods = [k for k in path_item.keys() if k.lower() in HTTP_METHODS]

    if not method:
        # No method specified
        if len(available_methods) == 1:
            method = available_methods[0].upper()
        else:
            raise FilteringError("Multiple methods under the selected path; add method= in [filtering]")
    else:
        # Method specified: check presence case-insensitively
        if method.lower() not in (m.lower() for m in available_methods):
            raise FilteringError(
                "Your spec does not contain either the required path or method. "
                "Specify the correct path and method in the [filtering] section of config.ini"
            )  # FR-006

    # Build a pruned spec:
    new_spec = {}
    # Keep top-level fields intact (FR-008)
    for k, v in spec_copy.items():
        if k != "paths":
            new_spec[k] = v

    # Keep only the selected path, and within it only the selected method
    pruned_path_item = {}
    # Preserve non-method siblings (e.g., path-level 'parameters') untouched
    for k, v in path_item.items():
        if k.lower() in HTTP_METHODS:
            if k.lower() == method.lower():
                pruned_path_item[k] = v
        else:
            pruned_path_item[k] = v

    new_spec["paths"] = {path: pruned_path_item}
    return new_spec
