"""Conditions to show a form field based on the values of other fields."""

from collections.abc import Mapping
from enum import StrEnum
import typing
from typing import Any, TypedDict, cast

import probatio


class ConditionOperator(StrEnum):
    """Operator comparing a field with the condition value."""

    EQ = "eq"
    NOT_EQ = "not_eq"
    IN = "in"
    NOT_IN = "not_in"
    EXISTS = "exists"
    NOT_EXISTS = "not_exists"


type ConditionValue = str | int | float | bool


class FieldCondition(TypedDict):
    """Condition on the value of another field of the same form."""

    field: str
    operator: typing.NotRequired[ConditionOperator]
    value: typing.NotRequired[ConditionValue | list[ConditionValue]]


_VALUE_SCHEMA = probatio.Any(str, int, float, bool)

CONDITION_SCHEMA = probatio.Any(
    probatio.Schema(
        {
            probatio.Required("field"): str,
            probatio.Optional("operator"): probatio.In(
                [ConditionOperator.EQ, ConditionOperator.NOT_EQ]
            ),
            probatio.Required("value"): _VALUE_SCHEMA,
        }
    ),
    probatio.Schema(
        {
            probatio.Required("field"): str,
            probatio.Required("operator"): probatio.In(
                [ConditionOperator.IN, ConditionOperator.NOT_IN]
            ),
            probatio.Required("value"): [_VALUE_SCHEMA],
        }
    ),
    probatio.Schema(
        {
            probatio.Required("field"): str,
            probatio.Required("operator"): probatio.In(
                [ConditionOperator.EXISTS, ConditionOperator.NOT_EXISTS]
            ),
        }
    ),
)

VISIBLE_SCHEMA = probatio.Any(bool, CONDITION_SCHEMA, [CONDITION_SCHEMA])


def evaluate_condition(condition: FieldCondition, data: Mapping[str, Any]) -> bool:
    """Evaluate a validated field condition against the values of the form."""
    actual = data.get(condition["field"])
    match condition.get("operator", ConditionOperator.EQ):
        case ConditionOperator.EQ:
            return condition["value"] == actual
        case ConditionOperator.NOT_EQ:
            return condition["value"] != actual
        case ConditionOperator.IN:
            return actual in cast(list[ConditionValue], condition["value"])
        case ConditionOperator.NOT_IN:
            return actual not in cast(list[ConditionValue], condition["value"])
        case ConditionOperator.EXISTS:
            return actual not in (None, "")
        case ConditionOperator.NOT_EXISTS:
            return actual in (None, "")


def is_field_visible(
    visible_condition: bool | FieldCondition | list[FieldCondition],
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
