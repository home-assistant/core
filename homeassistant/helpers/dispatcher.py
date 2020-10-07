"""Helpers for Home Assistant dispatcher & internal component/platform."""
import logging
from typing import Any, Callable

from homeassistant.core import HassJob, callback
from homeassistant.loader import bind_hass
from homeassistant.util.async_ import run_callback_threadsafe
from homeassistant.util.logging import catch_log_exception

from .typing import HomeAssistantType

_LOGGER = logging.getLogger(__name__)
DATA_DISPATCHER = "dispatcher"


@bind_hass
def dispatcher_connect(
    hass: HomeAssistantType, signal: str, target: Callable[..., None]
) -> Callable[[], None]:
    """Connect a callable function to a signal."""
    async_unsub = run_callback_threadsafe(
        hass.loop, async_dispatcher_connect, hass, signal, target
    ).result()

    def remove_dispatcher() -> None:
        """Remove signal listener."""
        run_callback_threadsafe(hass.loop, async_unsub).result()

    return remove_dispatcher


@callback
@bind_hass
def async_dispatcher_connect(
    hass: HomeAssistantType, signal: str, target: Callable[..., Any]
) -> Callable[[], None]:
    """Connect a callable function to a signal.

    This method must be run in the event loop.
    """
    if DATA_DISPATCHER not in hass.data:
        hass.data[DATA_DISPATCHER] = {}

    job = HassJob(
        catch_log_exception(
            target,
            lambda *args: "Exception in {} when dispatching '{}': {}".format(
                # Functions wrapped in partial do not have a __name__
                getattr(target, "__name__", None) or str(target),
                signal,
                args,
            ),
        )
    )

    hass.data[DATA_DISPATCHER].setdefault(signal, []).append(job)

    @callback
    def async_remove_dispatcher() -> None:
        """Remove signal listener."""
        try:
            hass.data[DATA_DISPATCHER][signal].remove(job)
        except (KeyError, ValueError):
            # KeyError is key target listener did not exist
            # ValueError if listener did not exist within signal
            _LOGGER.warning("Unable to remove unknown dispatcher %s", target)

    return async_remove_dispatcher


@bind_hass
def dispatcher_send(hass: HomeAssistantType, signal: str, *args: Any) -> None:
    """Send signal and data."""
    hass.loop.call_soon_threadsafe(async_dispatcher_send, hass, signal, *args)


@callback
@bind_hass
def async_dispatcher_send(hass: HomeAssistantType, signal: str, *args: Any) -> None:
    """Send signal and data.

    This method must be run in the event loop.
    """
    target_list = hass.data.get(DATA_DISPATCHER, {}).get(signal, [])

    for job in target_list:
        hass.async_add_hass_job(job, *args)
