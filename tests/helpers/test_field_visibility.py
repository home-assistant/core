"""Test field visibility conditions."""

from typing import Any

import probatio
import pytest

from homeassistant.helpers import field_visibility


@pytest.mark.parametrize(
    ("condition", "data", "expected"),
    [
        ({"field": "a", "value": 1}, {"a": 1}, True),
        ({"field": "a", "value": 1}, {"a": 2}, False),
        ({"field": "a", "operator": "eq", "value": "x"}, {"a": "x"}, True),
        ({"field": "a", "operator": "not_eq", "value": 1}, {"a": 2}, True),
        ({"field": "a", "operator": "not_eq", "value": 1}, {"a": 1}, False),
        ({"field": "a", "operator": "in", "value": [1, 2]}, {"a": 2}, True),
        ({"field": "a", "operator": "in", "value": [1, 2]}, {"a": 3}, False),
        ({"field": "a", "operator": "not_in", "value": [1, 2]}, {"a": 3}, True),
        ({"field": "a", "operator": "exists"}, {"a": "x"}, True),
        ({"field": "a", "operator": "exists"}, {"a": ""}, False),
        ({"field": "a", "operator": "exists"}, {}, False),
        ({"field": "a", "operator": "not_exists"}, {}, True),
        ({"field": "a", "operator": "not_exists"}, {"a": None}, True),
        ({"field": "a", "operator": "not_exists"}, {"a": 0}, False),
    ],
)
def test_evaluate_condition(condition: dict, data: dict, expected: bool) -> None:
    """Test conditions against the values of the form."""
    assert field_visibility.evaluate_condition(condition, data) is expected


@pytest.mark.parametrize(
    ("visible", "data", "expected"),
    [
        (True, {}, True),
        (False, {}, False),
        ([], {}, True),
        ({"field": "a", "value": 1}, {"a": 1}, True),
        ({"field": "a", "value": 1}, {"a": 2}, False),
        (
            [{"field": "a", "value": 1}, {"field": "b", "value": 2}],
            {"a": 1, "b": 2},
            True,
        ),
        (
            [{"field": "a", "value": 1}, {"field": "b", "value": 2}],
            {"a": 1, "b": 9},
            False,
        ),
    ],
)
def test_is_field_visible(
    visible: bool | dict | list, data: dict, expected: bool
) -> None:
    """Test visible condition resolution mirrors the frontend semantics."""
    assert field_visibility.is_field_visible(visible, data) is expected


@pytest.mark.parametrize(
    ("visible_by_field", "data", "expected"),
    [
        ({"b": {"field": "a", "value": 1}}, {"a": 1, "b": "x"}, set()),
        ({"b": {"field": "a", "value": 1}}, {"a": 2, "b": "x"}, {"b"}),
        (
            {
                "b": {"field": "a", "value": 1},
                "c": {"field": "b", "operator": "exists"},
            },
            {"a": 2, "b": "x", "c": "y"},
            {"b", "c"},
        ),
        (
            {"b": False, "c": {"field": "b", "operator": "not_exists"}},
            {"b": "x"},
            {"b"},
        ),
    ],
)
def test_get_hidden_fields(
    visible_by_field: dict[str, Any], data: dict[str, Any], expected: set[str]
) -> None:
    """Test a hidden field reads as absent to the conditions of other fields."""
    assert field_visibility.get_hidden_fields(visible_by_field, data) == expected


@pytest.mark.parametrize(
    "condition",
    [
        {"field": "a", "value": "x"},
        {"field": "a", "operator": "not_eq", "value": 1.5},
        {"field": "a", "operator": "in", "value": ["x", 1, True]},
        {"field": "a", "operator": "exists"},
    ],
)
def test_condition_schema(condition: dict[str, Any]) -> None:
    """Test valid conditions."""
    assert field_visibility.CONDITION_SCHEMA(condition) == condition


@pytest.mark.parametrize(
    "condition",
    [
        {"value": 1},
        {"field": "a"},
        {"field": "a", "value": None},
        {"field": "a", "operator": "in", "value": ["x", None]},
        {"field": "a", "operator": "gt", "value": 1},
        {"field": "a", "value": ["x"]},
        {"field": "a", "value": {"x": 1}},
        {"field": "a", "operator": "in", "value": "x"},
        {"field": "a", "operator": "in"},
        {"field": "a", "operator": "in", "value": [["x"]]},
        {"field": "a", "operator": "exists", "value": 1},
    ],
)
def test_condition_schema_invalid(condition: dict[str, Any]) -> None:
    """Test values must match the operator."""
    with pytest.raises(probatio.Invalid):
        field_visibility.CONDITION_SCHEMA(condition)
