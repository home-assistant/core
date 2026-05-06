"""Functional utility functions for Home Assistant templates."""

from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from operator import contains
import random
from typing import TYPE_CHECKING, Any

import jinja2
from jinja2 import pass_context

from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import ServiceResponse

from .base import BaseTemplateExtension, TemplateFunction

if TYPE_CHECKING:
    from homeassistant.helpers.template import TemplateEnvironment

_SENTINEL = object()


class FunctionalExtension(BaseTemplateExtension):
    """Jinja2 extension for functional utility functions."""

    def __init__(self, environment: TemplateEnvironment) -> None:
        """Initialize the functional extension."""
        super().__init__(
            environment,
            functions=[
                TemplateFunction(
                    "apply",
                    self.apply,
                    as_global=True,
                    as_filter=True,
                    as_test=True,
                ),
                TemplateFunction(
                    "as_function",
                    self.as_function,
                    as_global=True,
                    as_filter=True,
                ),
                TemplateFunction(
                    "iif",
                    self.iif,
                    as_global=True,
                    as_filter=True,
                ),
                TemplateFunction(
                    "merge_response",
                    self.merge_response,
                    as_global=True,
                ),
                TemplateFunction(
                    "combine",
                    self.combine,
                    as_global=True,
                    as_filter=True,
                ),
                TemplateFunction(
                    "typeof",
                    self.typeof,
                    as_global=True,
                    as_filter=True,
                ),
                TemplateFunction(
                    "is_defined",
                    self.fail_when_undefined,
                    as_filter=True,
                ),
                TemplateFunction(
                    "random",
                    _random_every_time,
                    as_filter=True,
                ),
                TemplateFunction(
                    "zip",
                    zip,
                    as_global=True,
                ),
                TemplateFunction(
                    "ord",
                    ord,
                    as_filter=True,
                ),
                TemplateFunction(
                    "contains",
                    contains,
                    as_filter=True,
                    as_test=True,
                ),
            ],
        )

    @staticmethod
    def apply(value: Any, fn: Any, *args: Any, **kwargs: Any) -> Any:
        """Call the given callable with the provided arguments and keyword arguments."""
        return fn(value, *args, **kwargs)

    @staticmethod
    def as_function(macro: jinja2.runtime.Macro) -> Callable[..., Any]:
        """Turn a macro with a 'returns' keyword argument into a function."""

        def wrapper(*args: Any, **kwargs: Any) -> Any:
            return_value = None

            def returns(value: Any) -> Any:
                nonlocal return_value
                return_value = value
                return value

            # Call the callable with the value and other args
            macro(*args, **kwargs, returns=returns)
            return return_value

        # Remove "macro_" from the macro's name to avoid confusion
        trimmed_name = macro.name.removeprefix("macro_")

        wrapper.__name__ = trimmed_name
        wrapper.__qualname__ = trimmed_name
        return wrapper

    @staticmethod
    def iif(
        value: Any,
        if_true: Any = True,
        if_false: Any = False,
        if_none: Any = _SENTINEL,
    ) -> Any:
        """Immediate if function/filter that allow for common if/else constructs.

        https://en.wikipedia.org/wiki/IIf

        Examples:
            {{ is_state("device_tracker.frenck", "home") | iif("yes", "no") }}
            {{ iif(1==2, "yes", "no") }}
            {{ (1 == 1) | iif("yes", "no") }}
        """
        if value is None and if_none is not _SENTINEL:
            return if_none
        if bool(value):
            return if_true
        return if_false

    @staticmethod
    def merge_response(value: ServiceResponse) -> list[Any]:
        """Merge action responses into single list.

        Checks that the input is a correct service response:
        {
            "entity_id": {str: dict[str, Any]},
        }
        If response is a single list, it will extend the list with the items
            and add the entity_id and value_key to each dictionary for reference.
        If response is a dictionary or multiple lists,
            it will append the dictionary/lists to the list
            and add the entity_id to each dictionary for reference.
        """
        if not isinstance(value, dict):
            raise TypeError("Response is not a dictionary")
        if not value:
            return []

        is_single_list = False
        response_items: list = []
        input_service_response = deepcopy(value)
        for entity_id, entity_response in input_service_response.items():  # pylint: disable=too-many-nested-blocks
            if not isinstance(entity_response, dict):
                raise TypeError("Response is not a dictionary")
            for value_key, type_response in entity_response.items():
                if len(entity_response) == 1 and isinstance(type_response, list):
                    is_single_list = True
                    for dict_in_list in type_response:
                        if isinstance(dict_in_list, dict):
                            if ATTR_ENTITY_ID in dict_in_list:
                                raise ValueError(
                                    f"Response dictionary already contains key '{ATTR_ENTITY_ID}'"
                                )
                            dict_in_list[ATTR_ENTITY_ID] = entity_id
                            dict_in_list["value_key"] = value_key
                    response_items.extend(type_response)
                else:
                    break

            if not is_single_list:
                _response = entity_response.copy()
                if ATTR_ENTITY_ID in _response:
                    raise ValueError(
                        f"Response dictionary already contains key '{ATTR_ENTITY_ID}'"
                    )
                _response[ATTR_ENTITY_ID] = entity_id
                response_items.append(_response)

        return response_items

    @staticmethod
    def combine(*args: Any, recursive: bool = False) -> dict[Any, Any]:
        """Combine multiple dictionaries into one."""
        if not args:
            raise TypeError("combine expected at least 1 argument, got 0")

        result: dict[Any, Any] = {}
        for arg in args:
            if not isinstance(arg, dict):
                raise TypeError(f"combine expected a dict, got {type(arg).__name__}")

            if recursive:
                for key, value in arg.items():
                    if (
                        key in result
                        and isinstance(result[key], dict)
                        and isinstance(value, dict)
                    ):
                        result[key] = FunctionalExtension.combine(
                            result[key], value, recursive=True
                        )
                    else:
                        result[key] = value
            else:
                result |= arg

        return result

    @staticmethod
    def typeof(value: Any) -> Any:
        """Return the type of value passed to debug types."""
        return value.__class__.__name__

    @staticmethod
    def fail_when_undefined(value: Any) -> Any:
        """Filter to force a failure when the value is undefined."""
        if isinstance(value, jinja2.Undefined):
            value()
        return value


@pass_context
def _random_every_time(context: Any, values: Any) -> Any:
    """Choose a random value.

    Unlike Jinja's random filter,
    this is context-dependent to avoid caching the chosen value.
    """
    return random.choice(values)
