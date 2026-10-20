"""Conditions to show a form field based on the values of other fields."""

from collections.abc import Mapping
from typing import Any, Literal, NotRequired, TypedDict, get_args

import probatio

ConditionOperator = Literal["eq", "not_eq", "in", "not_in", "exists", "not_exists"]


class FieldCondition(TypedDict):
    """Condition on the value of another field of the same form."""

    field: str
    operator: NotRequired[ConditionOperator]
    value: NotRequired[Any]


CONDITION_SCHEMA = probatio.Schema(
    {
        probatio.Required("field"): str,
        probatio.Optional("operator"): probatio.In(get_args(ConditionOperator)),
        probatio.Optional("value"): object,
    }
)

VISIBLE_SCHEMA = probatio.Any(bool, CONDITION_SCHEMA, [CONDITION_SCHEMA])


# Sentinel distinguishing an absent field from an explicit ``None`` value.
_MISSING = object()


def _condition_value_is_empty(value: Any) -> bool:
    return value is _MISSING or value is None or value == ""


def _strict_equal(actual: Any, value: Any) -> bool:
    """Compare by value and type, so a boolean never equals a number.

    A missing field and an omitted condition value are both undefined, so they
    equal each other but nothing else, and containers never compare equal,
    matching a renderer where a missing value is distinct from ``None`` and
    separately parsed lists or dicts are distinct references.
    """
    if actual is _MISSING or value is _MISSING:
        return actual is value
    if isinstance(actual, (list, tuple, dict)) or isinstance(
        value, (list, tuple, dict)
    ):
        return False
    if isinstance(actual, bool) != isinstance(value, bool):
        return False
    return bool(actual == value)


def evaluate_condition(condition: Mapping[str, Any], data: Mapping[str, Any]) -> bool:
    """Evaluate a field condition against submitted step data."""
    actual = data.get(condition["field"], _MISSING)
    value = condition.get("value", _MISSING)
    match condition.get("operator", "eq"):
        case "eq":
            return _strict_equal(actual, value)
        case "not_eq":
            return not _strict_equal(actual, value)
        case "in":
            return isinstance(value, (list, tuple)) and any(
                _strict_equal(actual, item) for item in value
            )
        case "not_in":
            return isinstance(value, (list, tuple)) and not any(
                _strict_equal(actual, item) for item in value
            )
        case "exists":
            return not _condition_value_is_empty(actual)
        case "not_exists":
            return _condition_value_is_empty(actual)
        case _:
            return False


def is_field_visible(
    visible_condition: bool | Mapping[str, Any] | list[Mapping[str, Any]],
    data: Mapping[str, Any],
) -> bool:
    """Return True when a field's visible condition matches the submitted data.

    A list of conditions is combined with AND.
    """
    if visible_condition is True:
        return True
    if visible_condition is False:
        return False
    # An empty list has no condition to fail, so the field is visible.
    conditions = (
        visible_condition
        if isinstance(visible_condition, list)
        else [visible_condition]
    )
    return all(evaluate_condition(condition, data) for condition in conditions)


def get_hidden_fields(
    visible_by_field: Mapping[str, Any], data: Mapping[str, Any]
) -> set[str]:
    """Return the fields whose visible condition does not match the data.

    Fields are hidden in order, and a hidden field reads as absent to the
    conditions of the other fields, matching the frontend.
    """
    values = dict(data)
    hidden: set[str] = set()
    changed = True
    while changed:
        changed = False
        for name, visible in visible_by_field.items():
            if name not in hidden and not is_field_visible(visible, values):
                hidden.add(name)
                values.pop(name, None)
                changed = True
    return hidden
