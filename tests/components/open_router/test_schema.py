"""Test conversion of structured output schemas."""

from copy import deepcopy
from typing import Any

import probatio
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.open_router.entity import _format_structured_output
from homeassistant.components.open_router.schema import adjust_schema
from homeassistant.exceptions import HomeAssistantError


@pytest.mark.parametrize(
    "field",
    [
        pytest.param({"type": "string"}, id="string"),
        pytest.param({"type": ["string", "integer"]}, id="multiple-types"),
        pytest.param({"type": ["string", "null"]}, id="nullable"),
        pytest.param({"type": "string", "enum": ["a", "b"]}, id="enum"),
        pytest.param(
            {"type": ["string", "null"], "enum": ["a", None]},
            id="nullable-enum",
        ),
        pytest.param({"enum": ["a", 1]}, id="untyped-enum"),
        pytest.param({"type": "string", "const": "a"}, id="constant"),
        pytest.param({"anyOf": [{"type": "string"}, {"type": "null"}]}, id="any-of"),
        pytest.param({"oneOf": [{"type": "string"}, {"type": "null"}]}, id="one-of"),
        pytest.param({"type": "string", "allOf": [{"enum": ["a", "b"]}]}, id="all-of"),
        pytest.param({"type": "string", "not": {"enum": [None, "b"]}}, id="negation"),
        pytest.param({"$ref": "#/$defs/value"}, id="reference"),
    ],
)
def test_optional_fields(field: dict[str, Any], snapshot: SnapshotAssertion) -> None:
    """Optional fields must accept null without weakening non-null constraints."""
    schema = {
        "type": "object",
        "properties": {"value": deepcopy(field)},
        "$defs": {"value": {"type": "string"}},
    }

    adjust_schema(schema)

    validator = probatio.from_json_schema(schema)
    validator({"value": None})
    validator({"value": "a"})
    with pytest.raises(probatio.Invalid):
        validator({})
    with pytest.raises(probatio.Invalid):
        validator({"value": []})
    assert schema == snapshot

    adjusted = deepcopy(schema)
    adjust_schema(schema)
    assert schema == adjusted


@pytest.mark.parametrize(
    "field",
    [
        pytest.param(True, id="true"),
        pytest.param(False, id="false"),
        pytest.param({}, id="empty"),
        pytest.param({"type": "null"}, id="null"),
    ],
)
def test_optional_untyped_fields(
    field: dict[str, Any] | bool, snapshot: SnapshotAssertion
) -> None:
    """Boolean, empty, and null schemas do not need a string type."""
    schema = {"type": "object", "properties": {"value": deepcopy(field)}}

    adjust_schema(schema)

    validator = probatio.from_json_schema(schema)
    validator({"value": None})
    with pytest.raises(probatio.Invalid):
        validator({})
    assert schema == snapshot


@pytest.mark.parametrize(
    "schema_type",
    [
        pytest.param("object", id="object"),
        pytest.param(["object", "null"], id="nullable"),
    ],
)
def test_nested_schemas(
    schema_type: str | list[str], snapshot: SnapshotAssertion
) -> None:
    """Visit nullable containers, union branches, and referenced definitions."""
    schema = {
        "type": schema_type,
        "properties": {
            "value": {"type": "string"},
            "children": {
                "type": ["array", "null"],
                "items": {"anyOf": [{"$ref": "#/$defs/child"}, {"type": "null"}]},
            },
        },
        "required": ["value"],
        "$defs": {
            "child": {"type": "object", "properties": {"name": {"type": "string"}}}
        },
    }

    adjust_schema(schema)

    validator = probatio.from_json_schema(schema)
    validator({"value": "a", "children": [{"name": None}, None]})
    with pytest.raises(probatio.Invalid):
        validator({"value": None, "children": None})
    with pytest.raises(probatio.Invalid):
        validator({"value": "a", "children": [{}]})
    assert schema == snapshot


@pytest.mark.parametrize(
    "field_order",
    [
        pytest.param(["value", "alias"], id="target-first"),
        pytest.param(["alias", "value"], id="alias-first"),
    ],
)
@pytest.mark.parametrize(
    ("target", "reference"),
    [
        pytest.param(
            {"anyOf": [{"type": "string"}, {"type": "integer"}]},
            "#/properties/value/anyOf/0",
            id="union-branch",
        ),
        pytest.param(
            {"type": "string"},
            "#/properties/value",
            id="optional-target",
        ),
        pytest.param(
            {"type": "object", "properties": {"a/b~c d": {"type": "string"}}},
            "#/properties/value/properties/a~1b~0c%20d",
            id="escaped-pointer",
        ),
    ],
)
def test_reference_targets(
    target: dict[str, Any], reference: str, field_order: list[str]
) -> None:
    """References retain their original constraints when targets become nullable."""
    fields = {"value": deepcopy(target), "alias": {"$ref": reference}}
    schema = {
        "type": "object",
        "properties": {name: fields[name] for name in field_order},
        "required": ["alias"],
    }

    adjust_schema(schema)

    validator = probatio.from_json_schema(schema)
    validator({"value": None, "alias": "a"})
    with pytest.raises(probatio.Invalid):
        validator({"value": None, "alias": 1})
    with pytest.raises(probatio.Invalid):
        validator({"value": None, "alias": None})


def test_recursive_reference_targets(snapshot: SnapshotAssertion) -> None:
    """Copied targets retain chained and recursive references without name collisions."""
    schema = {
        "type": "object",
        "properties": {
            "node": {
                "anyOf": [
                    {
                        "type": "object",
                        "properties": {
                            "value": {"$ref": "#/definitions/value"},
                            "child": {"$ref": "#/properties/node/anyOf/0"},
                        },
                        "required": ["value"],
                    },
                    {"type": "null"},
                ]
            },
            "alias": {"$ref": "#/properties/node/anyOf/0"},
        },
        "required": ["alias"],
        "definitions": {"value": {"type": "string"}},
        "$defs": {"_ha_ref_0": {"type": "integer"}},
        "examples": [{"$ref": "This is literal data"}],
    }

    adjust_schema(schema)

    validator = probatio.from_json_schema(schema)
    validator(
        {"node": None, "alias": {"value": "a", "child": {"value": "b", "child": None}}}
    )
    with pytest.raises(probatio.Invalid):
        validator({"node": None, "alias": {"value": None, "child": None}})
    assert schema == snapshot
    adjusted = deepcopy(schema)
    adjust_schema(schema)
    assert schema == adjusted


@pytest.mark.parametrize(
    "reference",
    [
        pytest.param("#/$defs/missing", id="missing"),
        pytest.param("https://example.com/schema", id="remote"),
        pytest.param("#/properties/value/anyOf/01", id="leading-zero"),
        pytest.param("#/properties/value/anyOf/-1", id="negative-index"),
        pytest.param("#/properties/value/anyOf/9", id="out-of-range"),
        pytest.param("#/properties/value/anyOf/0/type", id="non-schema-target"),
    ],
)
def test_invalid_reference(reference: str) -> None:
    """Invalid references fail before schema adjustments can obscure the cause."""
    schema = {
        "type": "object",
        "properties": {
            "value": {"anyOf": [{"type": "string"}]},
            "alias": {"$ref": reference},
        },
    }
    original = deepcopy(schema)

    with pytest.raises(HomeAssistantError, match="OpenRouter output schema reference"):
        adjust_schema(schema)

    assert schema == original


@pytest.mark.parametrize(
    "target",
    [pytest.param(True, id="true"), pytest.param(False, id="false")],
)
def test_boolean_reference_target(target: bool) -> None:
    """Boolean schema targets remain valid after moving to definitions."""
    schema = {
        "type": "object",
        "properties": {"value": target, "alias": {"$ref": "#/properties/value"}},
    }

    adjust_schema(schema)

    assert schema["$defs"] == {"_ha_ref_0": target}
    validator = probatio.from_json_schema(schema)
    validator({"value": None, "alias": None})


@pytest.mark.parametrize(
    "field",
    [
        pytest.param(probatio.Any(str, None), id="nullable-string"),
        pytest.param(probatio.Any({"name": str}, None), id="nullable-object"),
        pytest.param([probatio.Any({"name": str}, None)], id="array-of-unions"),
        pytest.param(probatio.In(["a", None]), id="nullable-enum"),
        pytest.param(probatio.ExactSequence([{"name": str}, int]), id="tuple"),
        pytest.param(probatio.Self, id="recursive-reference"),
    ],
)
def test_format_structured_output(field: object, snapshot: SnapshotAssertion) -> None:
    """Convert probatio schemas using OpenAPI 3.1, including nested schemas."""
    result = _format_structured_output("test", probatio.Schema({"value": field}), None)

    validator = probatio.from_json_schema(result["schema"])
    validator({"value": None})
    with pytest.raises(probatio.Invalid):
        validator({})
    assert result == snapshot


@pytest.mark.parametrize(
    ("name", "expected_name"),
    [
        pytest.param("Test Task", "test_task", id="spaces"),
        pytest.param("Прогноз погоды", "prognoz_pogody", id="unicode"),
        pytest.param("x" * 65, "x" * 64, id="length-limit"),
        pytest.param("!!!", "unknown", id="punctuation-only"),
        pytest.param("", "response", id="empty"),
    ],
)
def test_structured_output_name(name: str, expected_name: str) -> None:
    """User-provided task names satisfy the API's schema name restrictions."""
    result = _format_structured_output(name, probatio.Schema({"value": str}), None)

    assert result["name"] == expected_name
