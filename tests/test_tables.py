from api_description_tool.tables import (
    build_request_params_table,
    build_request_body_table,
    build_response_body_table,
    extract_constraints,
)


def test_request_params_table(valid_openapi_spec_dict):
    rows = build_request_params_table(valid_openapi_spec_dict, config={})
    assert rows, "expected at least one param row"
    r = rows[0]
    assert r["Name"] == "x-correlation-id"
    assert r["Mandatory"] is True
    assert r["In"] == "header"
    assert r["Expected Value(s)"] == "string"
    assert "Correlation id" in r["Description"]


def test_request_body_table_flattening(valid_openapi_spec_dict):
    rows = build_request_body_table(valid_openapi_spec_dict, config={})
    props = { (row["Path"], row["Property"]): row for row in rows }

    # top-level object properties (Path == "")
    assert ("", "name") in props
    assert props[("", "name")]["Mandatory"] is True
    # arrays flatten with [0]
    assert ("/tags[0]", None) not in props  # we expect the item properties resolved on items only
    assert any(r for r in rows if r["Path"] == "/tags[0]" and r["Property"] == "") is False
    # nested object path
    assert ("/owner", "first") in props

    # constraints exist in Expected Value(s)
    name_ev = props[("", "name")]["Expected Value(s)"]
    for part in ["string", "minLen=2", "pattern="]:
        assert part in name_ev


def test_response_body_table_status_and_flatten(valid_openapi_spec_dict):
    rows = build_response_body_table(valid_openapi_spec_dict, config={})
    assert any(r["Status"] == "200" for r in rows)
    assert any(r["Status"] == "default" for r in rows)
    # array items path notation
    assert any(r for r in rows if r["Path"].endswith("/kinds[0]"))


def test_extract_constraints_variants():
    assert extract_constraints({"type": "string"}) == "string"
    ev = extract_constraints(
        {"type": "string", "enum": ["a", "b"], "minLength": 1, "maxLength": 5, "pattern": "^x$"}
    )
    for token in ["string", "enum=a,b", "minLen=1", "maxLen=5", "pattern=^x$"]:
        assert token in ev