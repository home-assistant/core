"""Home Assistant debug mode."""
import asyncio
import functools
from typing import Callable

from requests.sessions import Session


def raise_in_loop() -> None:
    """Raise if called inside the event loop."""
    try:
        asyncio.current_task()
        in_loop = True
    except RuntimeError:
        in_loop = False

    if in_loop:
        raise RuntimeError("You cannot do I/O inside the event loop")


def protect_loop(func: Callable) -> None:
    """Protect function from running in event loop."""

    @functools.wraps(func)
    def protected_loop_func(*args, **kwargs):
        raise_in_loop()
        return func(*args, **kwargs)

    return protected_loop_func


def enable() -> None:
    """Enable debug mode."""
    Session.send = protect_loop(Session.send)
