"""Helper methods for various modules."""
import asyncio
from datetime import datetime, timedelta
import enum
from functools import wraps
import random
import re
import socket
import string
import threading
from types import MappingProxyType
from typing import (
    Any,
    Callable,
    Coroutine,
    Iterable,
    KeysView,
    Optional,
    TypeVar,
    Union,
)

import slugify as unicode_slug

from ..helpers.deprecation import deprecated_function
from .dt import as_local, utcnow

T = TypeVar("T")
U = TypeVar("U")  # pylint: disable=invalid-name
ENUM_T = TypeVar("ENUM_T", bound=enum.Enum)  # pylint: disable=invalid-name

RE_SANITIZE_FILENAME = re.compile(r"(~|\.\.|/|\\)")
RE_SANITIZE_PATH = re.compile(r"(~|\.(\.)+)")


def raise_if_invalid_filename(filename: str) -> None:
    """
    Check if a filename is valid.

    Raises a ValueError if the filename is invalid.
    """
    if RE_SANITIZE_FILENAME.sub("", filename) != filename:
        raise ValueError(f"{filename} is not a safe filename")


def raise_if_invalid_path(path: str) -> None:
    """
    Check if a path is valid.

    Raises a ValueError if the path is invalid.
    """
    if RE_SANITIZE_PATH.sub("", path) != path:
        raise ValueError(f"{path} is not a safe path")


@deprecated_function(replacement="raise_if_invalid_filename")
def sanitize_filename(filename: str) -> str:
    """Check if a filename is safe.

    Only to be used to compare to original filename to check if changed.
    If result changed, the given path is not safe and should not be used,
    raise an error.

    DEPRECATED.
    """
    # Backwards compatible fix for misuse of method
    if RE_SANITIZE_FILENAME.sub("", filename) != filename:
        return ""
    return filename


@deprecated_function(replacement="raise_if_invalid_path")
def sanitize_path(path: str) -> str:
    """Check if a path is safe.

    Only to be used to compare to original path to check if changed.
    If result changed, the given path is not safe and should not be used,
    raise an error.

    DEPRECATED.
    """
    # Backwards compatible fix for misuse of method
    if RE_SANITIZE_PATH.sub("", path) != path:
        return ""
    return path


def slugify(text: str, *, separator: str = "_") -> str:
    """Slugify a given text."""
    return unicode_slug.slugify(text, separator=separator)


def repr_helper(inp: Any) -> str:
    """Help creating a more readable string representation of objects."""
    if isinstance(inp, (dict, MappingProxyType)):
        return ", ".join(
            f"{repr_helper(key)}={repr_helper(item)}" for key, item in inp.items()
        )
    if isinstance(inp, datetime):
        return as_local(inp).isoformat()

    return str(inp)


def convert(
    value: Optional[T], to_type: Callable[[T], U], default: Optional[U] = None
) -> Optional[U]:
    """Convert value to to_type, returns default if fails."""
    try:
        return default if value is None else to_type(value)
    except (ValueError, TypeError):
        # If value could not be converted
        return default


def ensure_unique_string(
    preferred_string: str, current_strings: Union[Iterable[str], KeysView[str]]
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


# Taken from: http://stackoverflow.com/a/11735897
def get_local_ip() -> str:
    """Try to determine the local IP address of the machine."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        # Use Google Public DNS server to determine own IP
        sock.connect(("8.8.8.8", 80))

        return sock.getsockname()[0]  # type: ignore
    except OSError:
        try:
            return socket.gethostbyname(socket.gethostname())
        except socket.gaierror:
            return "127.0.0.1"
    finally:
        sock.close()


# Taken from http://stackoverflow.com/a/23728630
def get_random_string(length: int = 10) -> str:
    """Return a random string with letters and digits."""
    generator = random.SystemRandom()
    source_chars = string.ascii_letters + string.digits

    return "".join(generator.choice(source_chars) for _ in range(length))


class OrderedEnum(enum.Enum):
    """Taken from Python 3.4.0 docs."""

    # https://github.com/PyCQA/pylint/issues/2306
    # pylint: disable=comparison-with-callable

    def __ge__(self, other: ENUM_T) -> bool:
        """Return the greater than element."""
        if self.__class__ is other.__class__:
            return bool(self.value >= other.value)
        return NotImplemented

    def __gt__(self, other: ENUM_T) -> bool:
        """Return the greater element."""
        if self.__class__ is other.__class__:
            return bool(self.value > other.value)
        return NotImplemented

    def __le__(self, other: ENUM_T) -> bool:
        """Return the lower than element."""
        if self.__class__ is other.__class__:
            return bool(self.value <= other.value)
        return NotImplemented

    def __lt__(self, other: ENUM_T) -> bool:
        """Return the lower element."""
        if self.__class__ is other.__class__:
            return bool(self.value < other.value)
        return NotImplemented


class Throttle:
    """A class for throttling the execution of tasks.

    This method decorator adds a cooldown to a method to prevent it from being
    called more then 1 time within the timedelta interval `min_time` after it
    returned its result.

    Calling a method a second time during the interval will return None.

    Pass keyword argument `no_throttle=True` to the wrapped method to make
    the call not throttled.

    Decorator takes in an optional second timedelta interval to throttle the
    'no_throttle' calls.

    Adds a datetime attribute `last_call` to the method.
    """

    def __init__(
        self, min_time: timedelta, limit_no_throttle: Optional[timedelta] = None
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

            def throttled_value() -> None:  # type: ignore
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
            and "." not in method.__qualname__.split(".<locals>.")[-1]
        )

        @wraps(method)
        def wrapper(*args: Any, **kwargs: Any) -> Union[Callable, Coroutine]:
            """Wrap that allows wrapped to be called only once per min_time.

            If we cannot acquire the lock, it is running so return None.
            """
            if hasattr(method, "__self__"):
                host = getattr(method, "__self__")
            elif is_func:
                host = wrapper
            else:
                host = args[0] if args else wrapper

            # pylint: disable=protected-access # to _throttle
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
                if force or utcnow() - throttle[1] > self.min_time:
                    result = method(*args, **kwargs)
                    throttle[1] = utcnow()
                    return result  # type: ignore

                return throttled_value()
            finally:
                throttle[0].release()

        return wrapper
