"""Util functions to help filter out similar results."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta
import functools
from typing import Any, ParamSpec, TypeVar, overload

_R = TypeVar("_R", int, float, datetime)
_P = ParamSpec("_P")


@overload
def ignore_variance(
    func: Callable[_P, int], ignored_variance: int
) -> Callable[_P, int]: ...


@overload
def ignore_variance(
    func: Callable[_P, float], ignored_variance: float
) -> Callable[_P, float]: ...


@overload
def ignore_variance(
    func: Callable[_P, datetime], ignored_variance: timedelta
) -> Callable[_P, datetime]: ...


def ignore_variance(func: Callable[_P, _R], ignored_variance: Any) -> Callable[_P, _R]:
    """Wrap a function that returns old result if new result does not vary enough."""
    last_value: _R | None = None

    @functools.wraps(func)
    def wrapper(*args: _P.args, **kwargs: _P.kwargs) -> _R:
        nonlocal last_value

        value = func(*args, **kwargs)

        if last_value is not None and abs(value - last_value) < ignored_variance:
            return last_value

        last_value = value
        return value

    return wrapper
