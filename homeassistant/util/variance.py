"""Util functions to help filter out similar results."""
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta
import functools
from typing import Any, TypeVar, overload

T = TypeVar("T", int, float, datetime)


@overload
def ignore_variance(
    func: Callable[..., int], ignored_variance: int
) -> Callable[..., int]:
    ...


@overload
def ignore_variance(
    func: Callable[..., float], ignored_variance: float
) -> Callable[..., float]:
    ...


@overload
def ignore_variance(
    func: Callable[..., datetime], ignored_variance: timedelta
) -> Callable[..., datetime]:
    ...


def ignore_variance(func: Callable[..., T], ignored_variance: Any) -> Callable[..., T]:
    """Wrap a function that returns old result if new result does not vary enough."""
    last_value: T | None = None

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> T:
        nonlocal last_value

        value = func(*args, **kwargs)

        if last_value is not None and abs(value - last_value) < ignored_variance:
            return last_value

        last_value = value
        return value

    return wrapper
