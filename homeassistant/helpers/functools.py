"""Functools that are HA aware."""
import functools
from typing import Callable

from homeassistant.core import is_callback


def wraps(wrapped_func: Callable) -> Callable:
    """Decorate function to mimic wrapped function.

    Wraps copies all values set on a function. This can cause the callback decorator
    to be accidentally added to non-callback functions.
    """

    def wrap(to_wrap_func: Callable) -> Callable:
        """Wrap a function."""
        remove_callback = is_callback(wrapped_func) and not is_callback(to_wrap_func)
        wrapped = functools.wraps(wrapped_func)(to_wrap_func)

        if remove_callback:
            setattr(wrapped, "_hass_callback", False)

        return wrapped

    return wrap
