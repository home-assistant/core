"""Conditions to show a form field based on the values of other fields."""

from collections.abc import Mapping
import typing
from typing import Any, Literal, TypedDict, get_args

import probatio

ConditionOperator = Literal["eq", "not_eq", "in", "not_in", "exists", "not_exists"]


class FieldCondition(TypedDict):
    """Condition on the value of another field of the same form."""

    field: str
    operator: typing.NotRequired[ConditionOperator]
    value: typing.NotRequired[Any]


CONDITION_SCHEMA = probatio.Schema(
    {
        probatio.Required("field"): str,
        probatio.Optional("operator"): probatio.In(get_args(ConditionOperator)),
        probatio.Optional("value"): object,
    }
)

VISIBLE_SCHEMA = probatio.Any(bool, CONDITION_SCHEMA, [CONDITION_SCHEMA])


def _is_empty(value: Any) -> bool:
    return value is None or value == ""


def evaluate_condition(condition: Mapping[str, Any], data: Mapping[str, Any]) -> bool:
    """Evaluate a field condition against submitted step data."""
    actual = data.get(condition["field"])
    value = condition.get("value")
    match condition.get("operator", "eq"):
        case "eq":
            return bool(actual == value)
        case "not_eq":
            return bool(actual != value)
        case "in":
            return isinstance(value, (list, tuple)) and actual in value
        case "not_in":
            return isinstance(value, (list, tuple)) and actual not in value
        case "exists":
            return not _is_empty(actual)
        case "not_exists":
            return _is_empty(actual)
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
