"""Helpers for Home Assistant dispatcher & internal component/platform."""
import asyncio
import inspect
from functools import wraps
import logging
import traceback
from typing import Any, Callable

from homeassistant.core import callback
from homeassistant.loader import bind_hass
from homeassistant.util.async_ import run_callback_threadsafe
from .typing import HomeAssistantType


_LOGGER = logging.getLogger(__name__)
DATA_DISPATCHER = 'dispatcher'


@bind_hass
def dispatcher_connect(hass: HomeAssistantType, signal: str,
                       target: Callable[..., None]) -> Callable[[], None]:
    """Connect a callable function to a signal."""
    async_unsub = run_callback_threadsafe(
        hass.loop, async_dispatcher_connect, hass, signal, target).result()

    def remove_dispatcher() -> None:
        """Remove signal listener."""
        run_callback_threadsafe(hass.loop, async_unsub).result()

    return remove_dispatcher


def wrap_callback(func):
    """Decorate a signal callback to catch and log exceptions."""
    def log_exception(signal, *args):
        module_name = inspect.getmodule(inspect.trace()[1][0]).__name__
        # Do not print the wrapper in the traceback
        frames = len(inspect.trace()) - 1
        err = traceback.format_exc(-frames)
        logging.getLogger(module_name).error(
            "Exception in %s when dispatching '%s': '%s'\n%s",
            func.__name__, signal, *args, err)

    wrapper_func = None
    if asyncio.iscoroutinefunction(func):
        @wraps(func)
        async def wrapper(signal, *args):
            """Catch and log exception."""
            try:
                await func(*args)
            except Exception:  # pylint: disable=broad-except
                log_exception(signal, *args)
        wrapper_func = wrapper
    else:
        @wraps(func)
        def wrapper(signal, *args):
            """Catch and log exception."""
            try:
                func(*args)
            except Exception:  # pylint: disable=broad-except
                log_exception(signal, *args)
        wrapper_func = wrapper
    return wrapper_func


@callback
@bind_hass
def async_dispatcher_connect(hass: HomeAssistantType, signal: str,
                             target: Callable[..., Any]) -> Callable[[], None]:
    """Connect a callable function to a signal.

    This method must be run in the event loop.
    """
    if DATA_DISPATCHER not in hass.data:
        hass.data[DATA_DISPATCHER] = {}

    if signal not in hass.data[DATA_DISPATCHER]:
        hass.data[DATA_DISPATCHER][signal] = []

    wrapped_target = wrap_callback(target)

    hass.data[DATA_DISPATCHER][signal].append(wrapped_target)

    @callback
    def async_remove_dispatcher() -> None:
        """Remove signal listener."""
        try:
            hass.data[DATA_DISPATCHER][signal].remove(wrapped_target)
        except (KeyError, ValueError):
            # KeyError is key target listener did not exist
            # ValueError if listener did not exist within signal
            _LOGGER.warning(
                "Unable to remove unknown dispatcher %s", target)

    return async_remove_dispatcher


@bind_hass
def dispatcher_send(hass: HomeAssistantType, signal: str, *args: Any) -> None:
    """Send signal and data."""
    hass.loop.call_soon_threadsafe(async_dispatcher_send, hass, signal, *args)


@callback
@bind_hass
def async_dispatcher_send(
        hass: HomeAssistantType, signal: str, *args: Any) -> None:
    """Send signal and data.

    This method must be run in the event loop.
    """
    target_list = hass.data.get(DATA_DISPATCHER, {}).get(signal, [])

    for target in target_list:
        hass.async_add_job(target, signal, *args)
