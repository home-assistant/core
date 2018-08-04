"""Helper methods for various modules."""
import asyncio
from datetime import datetime, timedelta
from itertools import chain
import threading
import re
import enum
import socket
import random
import string
from functools import wraps
from types import MappingProxyType
from unicodedata import normalize

from typing import (Any, Optional, TypeVar, Callable, KeysView, Union,  # noqa
                    Iterable, List, Dict, Iterator, Coroutine, MutableSet)

from .dt import as_local, utcnow

# pylint: disable=invalid-name
T = TypeVar('T')
U = TypeVar('U')
ENUM_T = TypeVar('ENUM_T', bound=enum.Enum)
# pylint: enable=invalid-name

RE_SANITIZE_FILENAME = re.compile(r'(~|\.\.|/|\\)')
RE_SANITIZE_PATH = re.compile(r'(~|\.(\.)+)')
RE_SLUGIFY = re.compile(r'[^a-z0-9_]+')
TBL_SLUGIFY = {
    ord('ß'): 'ss'
}


def sanitize_filename(filename: str) -> str:
    r"""Sanitize a filename by removing .. / and \\."""
    return RE_SANITIZE_FILENAME.sub("", filename)


def sanitize_path(path: str) -> str:
    """Sanitize a path by removing ~ and .."""
    return RE_SANITIZE_PATH.sub("", path)


def slugify(text: str) -> str:
    """Slugify a given text."""
    text = normalize('NFKD', text)
    text = text.lower()
    text = text.replace(" ", "_")
    text = text.translate(TBL_SLUGIFY)
    text = RE_SLUGIFY.sub("", text)

    return text


def repr_helper(inp: Any) -> str:
    """Help creating a more readable string representation of objects."""
    if isinstance(inp, (dict, MappingProxyType)):
        return ", ".join(
            repr_helper(key)+"="+repr_helper(item) for key, item
            in inp.items())
    if isinstance(inp, datetime):
        return as_local(inp).isoformat()

    return str(inp)


def convert(value: T, to_type: Callable[[T], U],
            default: Optional[U] = None) -> Optional[U]:
    """Convert value to to_type, returns default if fails."""
    try:
        return default if value is None else to_type(value)
    except (ValueError, TypeError):
        # If value could not be converted
        return default


def ensure_unique_string(preferred_string: str, current_strings:
                         Union[Iterable[str], KeysView[str]]) -> str:
    """Return a string that is not present in current_strings.

    If preferred string exists will append _2, _3, ..
    """
    test_string = preferred_string
    current_strings_set = set(current_strings)

    tries = 1

    while test_string in current_strings_set:
        tries += 1
        test_string = "{}_{}".format(preferred_string, tries)

    return test_string


# Taken from: http://stackoverflow.com/a/11735897
def get_local_ip() -> str:
    """Try to determine the local IP address of the machine."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        # Use Google Public DNS server to determine own IP
        sock.connect(('8.8.8.8', 80))

        return sock.getsockname()[0]  # type: ignore
    except socket.error:
        try:
            return socket.gethostbyname(socket.gethostname())
        except socket.gaierror:
            return '127.0.0.1'
    finally:
        sock.close()


# Taken from http://stackoverflow.com/a/23728630
def get_random_string(length: int = 10) -> str:
    """Return a random string with letters and digits."""
    generator = random.SystemRandom()
    source_chars = string.ascii_letters + string.digits

    return ''.join(generator.choice(source_chars) for _ in range(length))


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


class OrderedSet(MutableSet[T]):
    """Ordered set taken from http://code.activestate.com/recipes/576694/."""

    def __init__(self, iterable: Iterable[T] = None) -> None:
        """Initialize the set."""
        self.end = end = []  # type: List[Any]
        end += [None, end, end]  # sentinel node for doubly linked list
        self.map = {}  # type: Dict[T, List] # key --> [key, prev, next]
        if iterable is not None:
            self |= iterable  # type: ignore

    def __len__(self) -> int:
        """Return the length of the set."""
        return len(self.map)

    def __contains__(self, key: T) -> bool:  # type: ignore
        """Check if key is in set."""
        return key in self.map

    # pylint: disable=arguments-differ
    def add(self, key: T) -> None:
        """Add an element to the end of the set."""
        if key not in self.map:
            end = self.end
            curr = end[1]
            curr[2] = end[1] = self.map[key] = [key, curr, end]

    def promote(self, key: T) -> None:
        """Promote element to beginning of the set, add if not there."""
        if key in self.map:
            self.discard(key)

        begin = self.end[2]
        curr = begin[1]
        curr[2] = begin[1] = self.map[key] = [key, curr, begin]

    # pylint: disable=arguments-differ
    def discard(self, key: T) -> None:
        """Discard an element from the set."""
        if key in self.map:
            key, prev_item, next_item = self.map.pop(key)
            prev_item[2] = next_item
            next_item[1] = prev_item

    def __iter__(self) -> Iterator[T]:
        """Iterate of the set."""
        end = self.end
        curr = end[2]
        while curr is not end:
            yield curr[0]
            curr = curr[2]

    def __reversed__(self) -> Iterator[T]:
        """Reverse the ordering."""
        end = self.end
        curr = end[1]
        while curr is not end:
            yield curr[0]
            curr = curr[1]

    # pylint: disable=arguments-differ
    def pop(self, last: bool = True) -> T:
        """Pop element of the end of the set.

        Set last=False to pop from the beginning.
        """
        if not self:
            raise KeyError('set is empty')
        key = self.end[1][0] if last else self.end[2][0]
        self.discard(key)
        return key  # type: ignore

    def update(self, *args: Any) -> None:
        """Add elements from args to the set."""
        for item in chain(*args):
            self.add(item)

    def __repr__(self) -> str:
        """Return the representation."""
        if not self:
            return '%s()' % (self.__class__.__name__,)
        return '%s(%r)' % (self.__class__.__name__, list(self))

    def __eq__(self, other: Any) -> bool:
        """Return the comparison."""
        if isinstance(other, OrderedSet):
            return len(self) == len(other) and list(self) == list(other)
        return set(self) == set(other)


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

    def __init__(self, min_time: timedelta,
                 limit_no_throttle: timedelta = None) -> None:
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
        is_func = (not hasattr(method, '__self__') and
                   '.' not in method.__qualname__.split('.<locals>.')[-1])

        @wraps(method)
        def wrapper(*args: Any, **kwargs: Any) -> Union[Callable, Coroutine]:
            """Wrap that allows wrapped to be called only once per min_time.

            If we cannot acquire the lock, it is running so return None.
            """
            # pylint: disable=protected-access
            if hasattr(method, '__self__'):
                host = getattr(method, '__self__')
            elif is_func:
                host = wrapper
            else:
                host = args[0] if args else wrapper

            if not hasattr(host, '_throttle'):
                host._throttle = {}

            if id(self) not in host._throttle:
                host._throttle[id(self)] = [threading.Lock(), None]
            throttle = host._throttle[id(self)]

            if not throttle[0].acquire(False):
                return throttled_value()

            # Check if method is never called or no_throttle is given
            force = kwargs.pop('no_throttle', False) or not throttle[1]

            try:
                if force or utcnow() - throttle[1] > self.min_time:
                    result = method(*args, **kwargs)
                    throttle[1] = utcnow()
                    return result  # type: ignore

                return throttled_value()
            finally:
                throttle[0].release()

        return wrapper
