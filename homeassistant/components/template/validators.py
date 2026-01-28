"""Template config validation methods."""

from collections.abc import Callable
from enum import StrEnum
import logging
from typing import Any

import voluptuous as vol

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

# Valid on/off values for booleans. These tuples are pulled
# from cv.boolean and are used to produce logger errors for the user.
RESULT_ON = ("1", "true", "yes", "on", "enable")
RESULT_OFF = ("0", "false", "no", "off", "disable")


def _log_validation_result_error(
    entity: Entity,
    attribute: str,
    value: Any,
    expected: tuple[str, ...] | str,
) -> None:
    """Log a template result error."""

    # in some cases, like `preview` entities, the entity_id does not exist.
    if entity.entity_id is None:
        message = f"Received invalid {attribute}: {value} for entity {entity.name}, %s"
    else:
        message = (
            f"Received invalid {entity.entity_id.split('.')[0]} {attribute}"
            f": {value} for entity {entity.entity_id}, %s"
        )

    _LOGGER.error(
        message,
        expected
        if isinstance(expected, str)
        else "expected one of " + ", ".join(expected),
    )


def _check_result_for_none(result: Any, **kwargs: Any) -> bool:
    """Checks the result for none, unknown, unavailable."""
    if result is None:
        return True

    if kwargs.get("none_on_unknown_unavailable") and isinstance(result, str):
        return result.lower() in (STATE_UNAVAILABLE, STATE_UNKNOWN)

    return False


def strenum[T: StrEnum](
    entity: Entity,
    attribute: str,
    state_enum: type[T],
    state_on: T | None = None,
    state_off: T | None = None,
    **kwargs: Any,
) -> Callable[[Any], T | None]:
    """Converts the template result to an StrEnum.

    All strings will attempt to convert to the StrEnum
    If state_on or state_off are provided, boolean values will return the
    enum that represents each boolean value.
    Anything that cannot convert will result in None.

    none_on_unknown_unavailable
    """

    def convert(result: Any) -> T | None:
        if _check_result_for_none(result, **kwargs):
            return None

        if isinstance(result, str):
            value = result.lower().strip()
            try:
                return state_enum(value)
            except ValueError:
                pass

        if state_on or state_off:
            try:
                bool_value = cv.boolean(result)
                if state_on and bool_value:
                    return state_on

                if state_off and not bool_value:
                    return state_off

            except vol.Invalid:
                pass

        expected = tuple(s.value for s in state_enum)
        if state_on:
            expected += RESULT_ON
        if state_off:
            expected += RESULT_OFF

        _log_validation_result_error(
            entity,
            attribute,
            result,
            expected,
        )
        return None

    return convert


def boolean(
    entity: Entity,
    attribute: str,
    as_true: tuple[str, ...] | None = None,
    as_false: tuple[str, ...] | None = None,
    **kwargs: Any,
) -> Callable[[Any], bool | None]:
    """Convert the result to a boolean.

    True/not 0/'1'/'true'/'yes'/'on'/'enable' are considered truthy
    False/0/'0'/'false'/'no'/'off'/'disable' are considered falsy
    Additional values provided by as_true are considered truthy
    Additional values provided by as_false are considered truthy
    All other values are None
    """

    def convert(result: Any) -> bool | None:
        if _check_result_for_none(result, **kwargs):
            return None

        if isinstance(result, bool):
            return result

        if isinstance(result, str) and (as_true or as_false):
            value = result.lower().strip()
            if as_true and value in as_true:
                return True
            if as_false and value in as_false:
                return False

        try:
            return cv.boolean(result)
        except vol.Invalid:
            pass

        items: tuple[str, ...] = RESULT_ON + RESULT_OFF
        if as_true:
            items += as_true
        if as_false:
            items += as_false

        _log_validation_result_error(entity, attribute, result, items)
        return None

    return convert


def number(
    entity: Entity,
    attribute: str,
    minimum: float | None = None,
    maximum: float | None = None,
    return_type: type[float] | type[int] = float,
    **kwargs: Any,
) -> Callable[[Any], float | int | None]:
    """Convert the result to a number (float or int).

    Any value in the range is converted to a float or int
    All other values are None
    """
    message = "expected a number"
    if minimum is not None and maximum is not None:
        message = f"{message} between {minimum:0.1f} and {maximum:0.1f}"
    elif minimum is not None and maximum is None:
        message = f"{message} greater than or equal to {minimum:0.1f}"
    elif minimum is None and maximum is not None:
        message = f"{message} less than or equal to {maximum:0.1f}"

    def convert(result: Any) -> float | int | None:
        if _check_result_for_none(result, **kwargs):
            return None

        if (result_type := type(result)) is bool:
            _log_validation_result_error(entity, attribute, result, message)
            return None

        if isinstance(result, (float, int)):
            value = result
            if return_type is int and result_type is float:
                value = int(value)
            elif return_type is float and result_type is int:
                value = float(value)
        else:
            try:
                value = vol.Coerce(float)(result)
                if return_type is int:
                    value = int(value)
            except vol.Invalid:
                _log_validation_result_error(entity, attribute, result, message)
                return None

        if minimum is None and maximum is None:
            return value

        if (
            (
                minimum is not None
                and maximum is not None
                and minimum <= value <= maximum
            )
            or (minimum is not None and maximum is None and value >= minimum)
            or (minimum is None and maximum is not None and value <= maximum)
        ):
            return value

        _log_validation_result_error(entity, attribute, result, message)
        return None

    return convert


def list_of_strings(
    entity: Entity,
    attribute: str,
    none_on_empty: bool = False,
    **kwargs: Any,
) -> Callable[[Any], list[str] | None]:
    """Convert the result to a list of strings.

    This ensures the result is a list of strings.
    All other values that are not lists will result in None.

    none_on_empty will cause the converter to return None when the list is empty.
    """

    def convert(result: Any) -> list[str] | None:
        if _check_result_for_none(result, **kwargs):
            return None

        if not isinstance(result, list):
            _log_validation_result_error(
                entity,
                attribute,
                result,
                "expected a list of strings",
            )
            return None

        if none_on_empty and len(result) == 0:
            return None

        # Ensure the result are strings.
        return [str(v) for v in result]

    return convert


def item_in_list[T](
    entity: Entity,
    attribute: str,
    items: list[Any] | None,
    items_attribute: str | None = None,
    **kwargs: Any,
) -> Callable[[Any], Any | None]:
    """Assert the result of the template is an item inside a list.

    Returns the result if the result is inside the list.
    All results that are not inside the list will return None.
    """

    def convert(result: Any) -> Any | None:
        if _check_result_for_none(result, **kwargs):
            return None

        # items may be mutable based on another template field. Always
        # perform this check when the items come from an configured
        # attribute.
        if items is None or (len(items) == 0):
            if items_attribute:
                _log_validation_result_error(
                    entity,
                    attribute,
                    result,
                    f"{items_attribute} is empty",
                )

            return None

        if result not in items:
            _log_validation_result_error(
                entity,
                attribute,
                result,
                tuple(str(v) for v in items),
            )
            return None

        return result

    return convert
