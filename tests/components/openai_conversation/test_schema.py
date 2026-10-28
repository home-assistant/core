"""Test conversion of structured output schemas."""

from copy import deepcopy
from typing import Any

import probatio
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.openai_conversation.entity import (
    _format_structured_output,
)
from homeassistant.components.openai_conversation.schema import adjust_schema
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import selector


@pytest.mark.parametrize(
    "field",
    [
        pytest.param({"type": "string"}, id="string"),
        pytest.param({"type": ["string", "null"]}, id="already-nullable"),
        pytest.param({"type": "string", "enum": ["a", "b"]}, id="enum"),
        pytest.param(
            {"type": ["string", "null"], "enum": ["a", None]}, id="nullable-enum"
        ),
        pytest.param({"type": "string", "const": "a"}, id="constant"),
        pytest.param({"anyOf": [{"type": "string"}, {"type": "integer"}]}, id="union"),
        pytest.param(
            {"type": "string", "anyOf": [{"enum": ["a", "b"]}]},
            id="constrained-union",
        ),
        pytest.param({"$ref": "#/$defs/value"}, id="reference"),
    ],
)
def test_optional_fields(field: dict[str, Any], snapshot: SnapshotAssertion) -> None:
    """Optional fields accept null while preserving their non-null constraints."""
    schema = {
        "type": "object",
        "properties": {"value": field},
        "$defs": {"value": {"type": "string", "enum": ["a", "b"]}},
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


def test_nested_references(snapshot: SnapshotAssertion) -> None:
    """Normalize referenced objects and unions without expanding recursive refs."""
    schema = {
        "type": "object",
        "properties": {"node": {"$ref": "#/$defs/node"}},
        "required": ["node"],
        "$defs": {
            "node": {
                "type": ["object", "null"],
                "properties": {
                    "value": {"type": "string"},
                    "children": {"type": "array", "items": {"$ref": "#/$defs/node"}},
                    "parent": {"$ref": "#"},
                    "variant": {
                        "anyOf": [
                            {
                                "type": "object",
                                "properties": {"name": {"type": "string"}},
                            },
                            {"type": "integer"},
                        ]
                    },
                },
            }
        },
    }
    adjust_schema(schema)

    validator = probatio.from_json_schema(schema)
    validator(
        {
            "node": {
                "value": "a",
                "children": [],
                "parent": None,
                "variant": {"name": "b"},
            }
        }
    )
    with pytest.raises(probatio.Invalid):
        validator({"node": {"value": "a"}})
    assert schema == snapshot


def test_recursive_reference_description(caplog: pytest.LogCaptureFixture) -> None:
    """Preserve a recursive field's description without expanding its reference."""
    schema = _format_structured_output(
        probatio.Schema(
            {
                probatio.Optional("child", description="The next node"): probatio.Self,
            }
        ),
        None,
    )

    assert schema["properties"]["child"] == {
        "anyOf": [{"$ref": "#"}, {"type": "null"}],
        "description": "The next node",
    }
    validator = probatio.from_json_schema(schema)
    validator({"child": {"child": None}})
    with pytest.raises(probatio.Invalid):
        validator({"child": {"child": "invalid"}})
    assert "Removed reference annotations" not in caplog.text


@pytest.mark.parametrize(
    "required",
    [pytest.param([], id="optional"), pytest.param(["value"], id="required")],
)
def test_reference_annotations(
    required: list[str], snapshot: SnapshotAssertion, caplog: pytest.LogCaptureFixture
) -> None:
    """Keep annotations on nullable wrappers and log removals elsewhere."""
    schema = {
        "type": "object",
        "properties": {
            "value": {
                "$ref": "#/$defs/value",
                "title": "Value",
                "description": "A value",
            }
        },
        "required": required.copy(),
        "$defs": {"value": {"type": "string", "enum": ["a", "b"]}},
    }
    adjust_schema(schema)

    assert schema == snapshot
    assert caplog.messages == snapshot(name="logs")
    validator = probatio.from_json_schema(schema)
    validator({"value": "a"})
    with pytest.raises(probatio.Invalid):
        validator({"value": "c"})


@pytest.mark.parametrize(
    "field",
    [
        pytest.param({"$ref": "#"}, id="required"),
        pytest.param({"type": "array", "items": {"$ref": "#"}}, id="array-items"),
    ],
)
def test_recursive_reference_annotations_removed(
    field: dict[str, Any], snapshot: SnapshotAssertion, caplog: pytest.LogCaptureFixture
) -> None:
    """Recursive references stay bare when no nullable wrapper is needed."""
    field = deepcopy(field)
    schema = {
        "type": "object",
        "properties": {"children": field},
        "required": ["children"],
    }
    target = field.get("items", field)
    target.update({"title": "Children", "description": "Child nodes"})
    adjust_schema(schema)

    assert schema == snapshot
    assert caplog.messages == snapshot(name="logs")


@pytest.mark.parametrize(
    "required",
    [pytest.param([], id="optional"), pytest.param(["value"], id="required")],
)
@pytest.mark.parametrize(
    ("field", "keyword"),
    [
        pytest.param(
            {"$ref": "#/$defs/value", "maxLength": 10}, "maxLength", id="length"
        ),
        pytest.param(
            {"$ref": "#/$defs/value", "allOf": [{"maxLength": 10}]},
            "maxLength",
            id="all-of",
        ),
        pytest.param(
            {"$ref": "#", "maxProperties": 1}, "maxProperties", id="recursive"
        ),
    ],
)
def test_reference_constraint_siblings(
    field: dict[str, Any], keyword: str, required: list[str]
) -> None:
    """Reject reference constraints instead of dropping them or expanding cycles."""
    with pytest.raises(HomeAssistantError, match="reference siblings") as err:
        adjust_schema(
            {
                "type": "object",
                "properties": {"value": deepcopy(field)},
                "required": required.copy(),
                "$defs": {"value": {"type": "string"}},
            }
        )
    assert "$.properties.value" in str(err.value)
    assert keyword in str(err.value)


@pytest.mark.parametrize(
    "field",
    [
        pytest.param(selector.EntitySelector(), id="entity"),
        pytest.param(selector.TemplateSelector(), id="template"),
        pytest.param(selector.CountrySelector(), id="country"),
        pytest.param(selector.LanguageSelector(), id="language"),
        pytest.param(selector.ColorRGBSelector(), id="rgb"),
        pytest.param(selector.DateSelector(), id="date"),
        pytest.param(selector.NumberSelector({"min": 0, "max": 120}), id="number"),
        pytest.param(selector.SelectSelector({"options": ["a", "b"]}), id="enum"),
        pytest.param(
            selector.SelectSelector({"options": ["a", "b"], "multiple": True}),
            id="multi-select",
        ),
        pytest.param(probatio.Any(str, int), id="union"),
    ],
)
def test_selector_schemas(
    field: selector.Selector | probatio.Any, snapshot: SnapshotAssertion
) -> None:
    """Convert actual selectors while preserving supported constraints."""
    schema = _format_structured_output(
        probatio.Schema({probatio.Optional("value"): field}), None
    )
    assert schema == snapshot


@pytest.mark.parametrize(
    ("field", "message"),
    [
        pytest.param(
            selector.ObjectSelector(),
            "explicitly defined object fields",
            id="free-object",
        ),
    ],
)
def test_unsupported_selectors(field: selector.Selector, message: str) -> None:
    """Reject constraints that cannot be preserved in strict output."""
    with pytest.raises(HomeAssistantError, match=message):
        _format_structured_output(
            probatio.Schema({probatio.Required("value"): field}), None
        )


@pytest.mark.parametrize(
    ("field", "message"),
    [
        pytest.param(
            {"allOf": [{"type": "string"}, {"type": "integer"}]}, "allOf", id="all-of"
        ),
        pytest.param(
            {"type": "string", "allOf": [{"type": "integer"}]},
            "Conflicting",
            id="conflicting-all-of",
        ),
        pytest.param({"type": "string", "not": {"enum": ["a"]}}, "not", id="not"),
        pytest.param({"type": "array"}, "array items", id="array-without-items"),
        pytest.param({}, "schema", id="unconstrained"),
        pytest.param(True, "schema", id="boolean-schema"),
    ],
)
def test_unsupported_schema(field: dict[str, Any] | bool, message: str) -> None:
    """Unsupported schemas fail locally with their field location."""
    with pytest.raises(HomeAssistantError, match=message) as err:
        adjust_schema({"type": "object", "properties": {"value": field}})
    assert "$.properties.value" in str(err.value)


@pytest.mark.parametrize(
    "schema",
    [
        pytest.param({"type": "array", "items": {"type": "string"}}, id="array"),
        pytest.param({"anyOf": [{"type": "object"}]}, id="union"),
    ],
)
def test_invalid_root(schema: dict[str, Any]) -> None:
    """Require an object at the root of a structured output schema."""
    with pytest.raises(HomeAssistantError, match="object root"):
        adjust_schema(schema)


@pytest.mark.parametrize(
    "field",
    [
        pytest.param(
            {
                "type": "string",
                "examples": ["a"],
                "$comment": "hint",
                "deprecated": False,
            },
            id="annotations",
        ),
        pytest.param(
            {"type": "array", "items": {"type": "string"}, "uniqueItems": False},
            id="no-uniqueness",
        ),
        pytest.param({"allOf": [{"type": "string"}]}, id="single-all-of"),
        pytest.param(
            {"minimum": 0, "allOf": [{"type": "number", "maximum": 5}]},
            id="all-of-siblings",
        ),
        pytest.param(
            {"type": "string", "format": "future-format", "futureConstraint": "new"},
            id="future-features",
        ),
    ],
)
def test_recoverable_schemas(
    field: dict[str, Any], snapshot: SnapshotAssertion
) -> None:
    """Recover safely and let the API decide whether it supports new features."""
    schema = {"type": "object", "properties": {"value": field}, "required": ["value"]}
    adjust_schema(schema)
    assert schema == snapshot


@pytest.mark.parametrize(
    "reference",
    [
        pytest.param("#/$defs/missing", id="missing"),
        pytest.param("https://example.com/schema", id="remote"),
        pytest.param("#/properties/value/anyOf/01", id="invalid-index"),
        pytest.param("#/properties/value/anyOf/9", id="out-of-range"),
    ],
)
def test_invalid_reference(reference: str) -> None:
    """Report invalid references before modifying their targets."""
    schema = {
        "type": "object",
        "properties": {
            "value": {"anyOf": [{"type": "string"}]},
            "alias": {"$ref": reference},
        },
    }
    with pytest.raises(HomeAssistantError, match="reference"):
        adjust_schema(schema)


@pytest.mark.parametrize("alias_first", [True, False])
@pytest.mark.parametrize(
    ("target", "reference"),
    [
        pytest.param(
            {"anyOf": [{"type": "string"}, {"type": "integer"}]},
            "#/properties/value/anyOf/0",
            id="array-pointer",
        ),
        pytest.param(
            {"const": {}, "type": "object", "properties": {"name": {"type": "string"}}},
            "#/properties/value/properties/name",
            id="moved-target",
        ),
        pytest.param(
            {"allOf": [{"type": "string"}]},
            "#/properties/value/allOf/0",
            id="unwrapped-target",
        ),
        pytest.param(
            {"type": "object", "properties": {"a/b~c d": {"type": "string"}}},
            "#/properties/value/properties/a~1b~0c%20d",
            id="escaped-pointer",
        ),
    ],
)
def test_reference_targets(
    target: dict[str, Any], reference: str, alias_first: bool
) -> None:
    """References keep their constraints regardless of traversal order or wrapping."""
    fields = [("value", deepcopy(target)), ("alias", {"$ref": "#/$defs/alias"})]
    fields.sort(key=lambda field: (field[0] == "alias") != alias_first)
    schema = {
        "type": "object",
        "$defs": {"alias": {"$ref": reference}},
        "properties": dict(fields),
        "required": ["alias"],
    }
    adjust_schema(schema)
    validator = probatio.from_json_schema(schema)
    validator({"value": None, "alias": "a"})
    with pytest.raises(probatio.Invalid):
        validator({"value": None, "alias": 1})
    with pytest.raises(probatio.Invalid):
        validator({"value": None, "alias": None})
