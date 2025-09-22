"""Mathematical and statistical functions for Home Assistant templates."""

from __future__ import annotations

from collections.abc import Iterable
from functools import wraps
import math
import statistics
from typing import TYPE_CHECKING, Any

import jinja2
from jinja2 import pass_environment

from homeassistant.helpers.template.helpers import raise_no_default

from .base import BaseTemplateExtension, TemplateFunction

if TYPE_CHECKING:
    from homeassistant.helpers.template import TemplateEnvironment

# Sentinel object for default parameter
_SENTINEL = object()


class MathExtension(BaseTemplateExtension):
    """Jinja2 extension for mathematical and statistical functions."""

    def __init__(self, environment: TemplateEnvironment) -> None:
        """Initialize the math extension."""
        super().__init__(
            environment,
            functions=[
                # Math constants (as globals only) - these are values, not functions
                TemplateFunction("e", math.e, as_global=True),
                TemplateFunction("pi", math.pi, as_global=True),
                TemplateFunction("tau", math.pi * 2, as_global=True),
                # Trigonometric functions (as globals and filters)
                TemplateFunction("sin", self.sine, as_global=True, as_filter=True),
                TemplateFunction("cos", self.cosine, as_global=True, as_filter=True),
                TemplateFunction("tan", self.tangent, as_global=True, as_filter=True),
                TemplateFunction("asin", self.arc_sine, as_global=True, as_filter=True),
                TemplateFunction(
                    "acos", self.arc_cosine, as_global=True, as_filter=True
                ),
                TemplateFunction(
                    "atan", self.arc_tangent, as_global=True, as_filter=True
                ),
                TemplateFunction(
                    "atan2", self.arc_tangent2, as_global=True, as_filter=True
                ),
                # Advanced math functions (as globals and filters)
                TemplateFunction("log", self.logarithm, as_global=True, as_filter=True),
                TemplateFunction(
                    "sqrt", self.square_root, as_global=True, as_filter=True
                ),
                # Statistical functions (as globals and filters)
                TemplateFunction(
                    "average", self.average, as_global=True, as_filter=True
                ),
                TemplateFunction("median", self.median, as_global=True, as_filter=True),
                TemplateFunction(
                    "statistical_mode",
                    self.statistical_mode,
                    as_global=True,
                    as_filter=True,
                ),
                # Min/Max functions (as globals only)
                TemplateFunction("min", self.min_max_min, as_global=True),
                TemplateFunction("max", self.min_max_max, as_global=True),
                # Bitwise operations (as globals and filters)
                TemplateFunction(
                    "bitwise_and", self.bitwise_and, as_global=True, as_filter=True
                ),
                TemplateFunction(
                    "bitwise_or", self.bitwise_or, as_global=True, as_filter=True
                ),
                TemplateFunction(
                    "bitwise_xor", self.bitwise_xor, as_global=True, as_filter=True
                ),
            ],
        )

    @staticmethod
    def logarithm(value: Any, base: Any = math.e, default: Any = _SENTINEL) -> Any:
        """Filter and function to get logarithm of the value with a specific base."""
        try:
            base_float = float(base)
        except (ValueError, TypeError):
            if default is _SENTINEL:
                raise_no_default("log", base)
            return default
        try:
            value_float = float(value)
            return math.log(value_float, base_float)
        except (ValueError, TypeError):
            if default is _SENTINEL:
                raise_no_default("log", value)
            return default

    @staticmethod
    def sine(value: Any, default: Any = _SENTINEL) -> Any:
        """Filter and function to get sine of the value."""
        try:
            return math.sin(float(value))
        except (ValueError, TypeError):
            if default is _SENTINEL:
                raise_no_default("sin", value)
            return default

    @staticmethod
    def cosine(value: Any, default: Any = _SENTINEL) -> Any:
        """Filter and function to get cosine of the value."""
        try:
            return math.cos(float(value))
        except (ValueError, TypeError):
            if default is _SENTINEL:
                raise_no_default("cos", value)
            return default

    @staticmethod
    def tangent(value: Any, default: Any = _SENTINEL) -> Any:
        """Filter and function to get tangent of the value."""
        try:
            return math.tan(float(value))
        except (ValueError, TypeError):
            if default is _SENTINEL:
                raise_no_default("tan", value)
            return default

    @staticmethod
    def arc_sine(value: Any, default: Any = _SENTINEL) -> Any:
        """Filter and function to get arc sine of the value."""
        try:
            return math.asin(float(value))
        except (ValueError, TypeError):
            if default is _SENTINEL:
                raise_no_default("asin", value)
            return default

    @staticmethod
    def arc_cosine(value: Any, default: Any = _SENTINEL) -> Any:
        """Filter and function to get arc cosine of the value."""
        try:
            return math.acos(float(value))
        except (ValueError, TypeError):
            if default is _SENTINEL:
                raise_no_default("acos", value)
            return default

    @staticmethod
    def arc_tangent(value: Any, default: Any = _SENTINEL) -> Any:
        """Filter and function to get arc tangent of the value."""
        try:
            return math.atan(float(value))
        except (ValueError, TypeError):
            if default is _SENTINEL:
                raise_no_default("atan", value)
            return default

    @staticmethod
    def arc_tangent2(*args: Any, default: Any = _SENTINEL) -> Any:
        """Filter and function to calculate four quadrant arc tangent of y / x.

        The parameters to atan2 may be passed either in an iterable or as separate arguments
        The default value may be passed either as a positional or in a keyword argument
        """
        try:
            if 1 <= len(args) <= 2 and isinstance(args[0], (list, tuple)):
                if len(args) == 2 and default is _SENTINEL:
                    # Default value passed as a positional argument
                    default = args[1]
                args = tuple(args[0])
            elif len(args) == 3 and default is _SENTINEL:
                # Default value passed as a positional argument
                default = args[2]

            return math.atan2(float(args[0]), float(args[1]))
        except (ValueError, TypeError):
            if default is _SENTINEL:
                raise_no_default("atan2", args)
            return default

    @staticmethod
    def square_root(value: Any, default: Any = _SENTINEL) -> Any:
        """Filter and function to get square root of the value."""
        try:
            return math.sqrt(float(value))
        except (ValueError, TypeError):
            if default is _SENTINEL:
                raise_no_default("sqrt", value)
            return default

    @staticmethod
    def average(*args: Any, default: Any = _SENTINEL) -> Any:
        """Filter and function to calculate the arithmetic mean.

        Calculates of an iterable or of two or more arguments.

        The parameters may be passed as an iterable or as separate arguments.
        """
        if len(args) == 0:
            raise TypeError("average expected at least 1 argument, got 0")

        # If first argument is iterable and more than 1 argument provided but not a named
        # default, then use 2nd argument as default.
        if isinstance(args[0], Iterable):
            average_list = args[0]
            if len(args) > 1 and default is _SENTINEL:
                default = args[1]
        elif len(args) == 1:
            raise TypeError(f"'{type(args[0]).__name__}' object is not iterable")
        else:
            average_list = args

        try:
            return statistics.fmean(average_list)
        except (TypeError, statistics.StatisticsError):
            if default is _SENTINEL:
                raise_no_default("average", args)
            return default

    @staticmethod
    def median(*args: Any, default: Any = _SENTINEL) -> Any:
        """Filter and function to calculate the median.

        Calculates median of an iterable of two or more arguments.

        The parameters may be passed as an iterable or as separate arguments.
        """
        if len(args) == 0:
            raise TypeError("median expected at least 1 argument, got 0")

        # If first argument is a list or tuple and more than 1 argument provided but not a named
        # default, then use 2nd argument as default.
        if isinstance(args[0], Iterable):
            median_list = args[0]
            if len(args) > 1 and default is _SENTINEL:
                default = args[1]
        elif len(args) == 1:
            raise TypeError(f"'{type(args[0]).__name__}' object is not iterable")
        else:
            median_list = args

        try:
            return statistics.median(median_list)
        except (TypeError, statistics.StatisticsError):
            if default is _SENTINEL:
                raise_no_default("median", args)
            return default

    @staticmethod
    def statistical_mode(*args: Any, default: Any = _SENTINEL) -> Any:
        """Filter and function to calculate the statistical mode.

        Calculates mode of an iterable of two or more arguments.

        The parameters may be passed as an iterable or as separate arguments.
        """
        if not args:
            raise TypeError("statistical_mode expected at least 1 argument, got 0")

        # If first argument is a list or tuple and more than 1 argument provided but not a named
        # default, then use 2nd argument as default.
        if len(args) == 1 and isinstance(args[0], Iterable):
            mode_list = args[0]
        elif isinstance(args[0], list | tuple):
            mode_list = args[0]
            if len(args) > 1 and default is _SENTINEL:
                default = args[1]
        elif len(args) == 1:
            raise TypeError(f"'{type(args[0]).__name__}' object is not iterable")
        else:
            mode_list = args

        try:
            return statistics.mode(mode_list)
        except (TypeError, statistics.StatisticsError):
            if default is _SENTINEL:
                raise_no_default("statistical_mode", args)
            return default

    def min_max_from_filter(self, builtin_filter: Any, name: str) -> Any:
        """Convert a built-in min/max Jinja filter to a global function.

        The parameters may be passed as an iterable or as separate arguments.
        """

        @pass_environment
        @wraps(builtin_filter)
        def wrapper(environment: jinja2.Environment, *args: Any, **kwargs: Any) -> Any:
            if len(args) == 0:
                raise TypeError(f"{name} expected at least 1 argument, got 0")

            if len(args) == 1:
                if isinstance(args[0], Iterable):
                    return builtin_filter(environment, args[0], **kwargs)

                raise TypeError(f"'{type(args[0]).__name__}' object is not iterable")

            return builtin_filter(environment, args, **kwargs)

        return pass_environment(wrapper)

    def min_max_min(self, *args: Any, **kwargs: Any) -> Any:
        """Min function using built-in filter."""
        return self.min_max_from_filter(self.environment.filters["min"], "min")(
            self.environment, *args, **kwargs
        )

    def min_max_max(self, *args: Any, **kwargs: Any) -> Any:
        """Max function using built-in filter."""
        return self.min_max_from_filter(self.environment.filters["max"], "max")(
            self.environment, *args, **kwargs
        )

    @staticmethod
    def bitwise_and(first_value: Any, second_value: Any) -> Any:
        """Perform a bitwise and operation."""
        return first_value & second_value

    @staticmethod
    def bitwise_or(first_value: Any, second_value: Any) -> Any:
        """Perform a bitwise or operation."""
        return first_value | second_value

    @staticmethod
    def bitwise_xor(first_value: Any, second_value: Any) -> Any:
        """Perform a bitwise xor operation."""
        return first_value ^ second_value
