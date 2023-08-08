"""Helper methods for various modules."""
from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine, Iterable, KeysView, Mapping
from datetime import datetime, timedelta
from functools import wraps
import random
import re
import string
import threading
from typing import Any, TypeVar

import slugify as unicode_slug

from . import dt as dt_util

_T = TypeVar("_T")
_U = TypeVar("_U")

RE_SANITIZE_FILENAME = re.compile(r"(~|\.\.|/|\\)")
RE_SANITIZE_PATH = re.compile(r"(~|\.(\.)+)")


def raise_if_invalid_filename(filename: str) -> None:
    """Check if a filename is valid.

    Raises a ValueError if the filename is invalid.
    """
    if RE_SANITIZE_FILENAME.sub("", filename) != filename:
        raise ValueError(f"{filename} is not a safe filename")


def raise_if_invalid_path(path: str) -> None:
    """Check if a path is valid.

    Raises a ValueError if the path is invalid.
    """
    if RE_SANITIZE_PATH.sub("", path) != path:
        raise ValueError(f"{path} is not a safe path")


def slugify(text: str | None, *, separator: str = "_") -> str:
    """Slugify a given text."""
    if text == "" or text is None:
        return ""
    slug = unicode_slug.slugify(text, separator=separator)
    return "unknown" if slug == "" else slug


def repr_helper(inp: Any) -> str:
    """Help creating a more readable string representation of objects."""
    if isinstance(inp, Mapping):
        return ", ".join(
            f"{repr_helper(key)}={repr_helper(item)}" for key, item in inp.items()
        )
    if isinstance(inp, datetime):
        return dt_util.as_local(inp).isoformat()

    return str(inp)


def convert(
    value: _T | None, to_type: Callable[[_T], _U], default: _U | None = None
) -> _U | None:
    """Convert value to to_type, returns default if fails."""
    try:
        return default if value is None else to_type(value)
    except (ValueError, TypeError):
        # If value could not be converted
        return default


def ensure_unique_string(
    preferred_string: str, current_strings: Iterable[str] | KeysView[str]
) -> str:
    """Return a string that is not present in current_strings.

    If preferred string exists will append _2, _3, ..
    """
    test_string = preferred_string
    current_strings_set = set(current_strings)

    tries = 1

    while test_string in current_strings_set:
        tries += 1
        test_string = f"{preferred_string}_{tries}"

    return test_string


# Taken from http://stackoverflow.com/a/23728630
def get_random_string(length: int = 10) -> str:
    """Return a random string with letters and digits."""
    generator = random.SystemRandom()
    source_chars = string.ascii_letters + string.digits

    return "".join(generator.choice(source_chars) for _ in range(length))


class Throttle:
    """A class for throttling the execution of tasks.

    This method decorator adds a cooldown to a method to prevent it from being
    called more than 1 time within the timedelta interval `min_time` after it
    returned its result.

    Calling a method a second time during the interval will return None.

    Pass keyword argument `no_throttle=True` to the wrapped method to make
    the call not throttled.

    Decorator takes in an optional second timedelta interval to throttle the
    'no_throttle' calls.

    Adds a datetime attribute `last_call` to the method.
    """

    def __init__(
        self, min_time: timedelta, limit_no_throttle: timedelta | None = None
    ) -> None:
        """Initialize the throttle."""
        self.min_time = min_time
        self.limit_no_throttle = limit_no_throttle

    def __call__(self, method: Callable) -> Callable:
        """Caller for the throttle."""
        # Make sure we return a coroutine if the method is async.
        if asyncio.iscoroutinefunction(method):

            async def throttled_value() -> None:
                """Stand-in function for when real func is being throttled."""
                return None

        else:

            def throttled_value() -> None:  # type: ignore[misc]
                """Stand-in function for when real func is being throttled."""
                return None

        if self.limit_no_throttle is not None:
            method = Throttle(self.limit_no_throttle)(method)

        # Different methods that can be passed in:
        #  - a function
        #  - an unbound function on a class
        #  - a method (bound function on a class)

        # We want to be able to differentiate between function and unbound
        # methods (which are considered functions).
        # All methods have the classname in their qualname separated by a '.'
        # Functions have a '.' in their qualname if defined inline, but will
        # be prefixed by '.<locals>.' so we strip that out.
        is_func = (
            not hasattr(method, "__self__")
            and "." not in method.__qualname__.rpartition(".<locals>.")[-1]
        )

        @wraps(method)
        def wrapper(*args: Any, **kwargs: Any) -> Callable | Coroutine:
            """Wrap that allows wrapped to be called only once per min_time.

            If we cannot acquire the lock, it is running so return None.
            """
            if hasattr(method, "__self__"):
                host = getattr(method, "__self__")
            elif is_func:
                host = wrapper
            else:
                host = args[0] if args else wrapper

            # pylint: disable=protected-access
            if not hasattr(host, "_throttle"):
                host._throttle = {}

            if id(self) not in host._throttle:
                host._throttle[id(self)] = [threading.Lock(), None]
            throttle = host._throttle[id(self)]
            # pylint: enable=protected-access

            if not throttle[0].acquire(False):
                return throttled_value()

            # Check if method is never called or no_throttle is given
            force = kwargs.pop("no_throttle", False) or not throttle[1]

            try:
                if force or dt_util.utcnow() - throttle[1] > self.min_time:
                    result = method(*args, **kwargs)
                    throttle[1] = dt_util.utcnow()
                    return result  # type: ignore[no-any-return]

                return throttled_value()
            finally:
                throttle[0].release()

        return wrapper
