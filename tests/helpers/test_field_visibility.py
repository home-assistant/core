"""Test field visibility conditions."""

from typing import Any

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
        # a missing field reads as None
        ({"field": "a", "value": None}, {}, True),
        ({"field": "a"}, {"a": "x"}, False),
        ({"field": "a", "operator": "not_eq"}, {"a": "x"}, True),
        ({"field": "a", "value": ["x"]}, {"a": ["x"]}, True),
        ({"field": "a", "operator": "in", "value": [1, 2]}, {"a": 2}, True),
        ({"field": "a", "operator": "in", "value": [1, 2]}, {"a": 3}, False),
        ({"field": "a", "operator": "in", "value": "notalist"}, {"a": "n"}, False),
        ({"field": "a", "operator": "not_in", "value": [1, 2]}, {"a": 3}, True),
        ({"field": "a", "operator": "exists"}, {"a": "x"}, True),
        ({"field": "a", "operator": "exists"}, {"a": ""}, False),
        ({"field": "a", "operator": "exists"}, {}, False),
        ({"field": "a", "operator": "not_exists"}, {}, True),
        ({"field": "a", "operator": "not_exists"}, {"a": None}, True),
        ({"field": "a", "operator": "not_exists"}, {"a": 0}, False),
        ({"field": "a", "operator": "unknown"}, {"a": 1}, False),
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
