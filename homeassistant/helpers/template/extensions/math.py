"""Mathematical and statistical functions for Home Assistant templates."""

from __future__ import annotations

from collections.abc import Iterable
from functools import wraps
import math
import statistics
from typing import TYPE_CHECKING, Any, Literal

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
                # Value constraint functions (as globals and filters)
                TemplateFunction("clamp", self.clamp, as_global=True, as_filter=True),
                TemplateFunction("wrap", self.wrap, as_global=True, as_filter=True),
                TemplateFunction("remap", self.remap, as_global=True, as_filter=True),
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

    @staticmethod
    def clamp(value: Any, min_value: Any, max_value: Any) -> Any:
        """Filter and function to clamp a value between min and max bounds.

        Constrains value to the range [min_value, max_value] (inclusive).
        """
        try:
            value_num = float(value)
            min_value_num = float(min_value)
            max_value_num = float(max_value)
        except (ValueError, TypeError) as err:
            raise ValueError(
                f"function requires numeric arguments, "
                f"got {value=}, {min_value=}, {max_value=}"
            ) from err
        return max(min_value_num, min(max_value_num, value_num))

    @staticmethod
    def wrap(value: Any, min_value: Any, max_value: Any) -> Any:
        """Filter and function to wrap a value within a range.

        Wraps value cyclically within [min_value, max_value) (inclusive min, exclusive max).
        """
        try:
            value_num = float(value)
            min_value_num = float(min_value)
            max_value_num = float(max_value)
        except (ValueError, TypeError) as err:
            raise ValueError(
                f"function requires numeric arguments, "
                f"got {value=}, {min_value=}, {max_value=}"
            ) from err
        try:
            range_size = max_value_num - min_value_num
            return ((value_num - min_value_num) % range_size) + min_value_num
        except ZeroDivisionError:  # be lenient: if the range is empty, just clamp
            return min_value_num

    @staticmethod
    def remap(
        value: Any,
        in_min: Any,
        in_max: Any,
        out_min: Any,
        out_max: Any,
        *,
        steps: int = 0,
        edges: Literal["none", "clamp", "wrap", "mirror"] = "none",
    ) -> Any:
        """Filter and function to remap a value from one range to another.

        Maps value from input range [in_min, in_max] to output range [out_min, out_max].

        The steps parameter, if greater than 0, quantizes the output into
        the specified number of discrete steps.

        The edges parameter controls how out-of-bounds input values are handled:
        - "none": No special handling; values outside the input range are extrapolated into the output range.
        - "clamp": Values outside the input range are clamped to the nearest boundary.
        - "wrap": Values outside the input range are wrapped around cyclically.
        - "mirror": Values outside the input range are mirrored back into the range.
        """
        try:
            value_num = float(value)
            in_min_num = float(in_min)
            in_max_num = float(in_max)
            out_min_num = float(out_min)
            out_max_num = float(out_max)
        except (ValueError, TypeError) as err:
            raise ValueError(
                f"function requires numeric arguments, "
                f"got {value=}, {in_min=}, {in_max=}, {out_min=}, {out_max=}"
            ) from err

        # Apply edge behavior in original space for accuracy.
        if edges == "clamp":
            value_num = max(in_min_num, min(in_max_num, value_num))
        elif edges == "wrap":
            if in_min_num == in_max_num:
                raise ValueError(f"{in_min=} must not equal {in_max=}")

            range_size = in_max_num - in_min_num  # Validated against div0 above.
            value_num = ((value_num - in_min_num) % range_size) + in_min_num
        elif edges == "mirror":
            if in_min_num == in_max_num:
                raise ValueError(f"{in_min=} must not equal {in_max=}")

            range_size = in_max_num - in_min_num  # Validated against div0 above.
            # Determine which period we're in and whether it should be mirrored
            offset = value_num - in_min_num
            period = math.floor(offset / range_size)
            position_in_period = offset - (period * range_size)

            if (period < 0) or (period % 2 != 0):
                position_in_period = range_size - position_in_period

            value_num = in_min_num + position_in_period
        # Unknown "edges" values are left as-is; no use throwing an error.

        steps = max(steps, 0)

        if not steps and (in_min_num == out_min_num and in_max_num == out_max_num):
            return value_num  # No remapping needed. Save some cycles and floating-point precision.

        normalized = (value_num - in_min_num) / (in_max_num - in_min_num)

        if steps:
            normalized = round(normalized * steps) / steps

        return out_min_num + (normalized * (out_max_num - out_min_num))
