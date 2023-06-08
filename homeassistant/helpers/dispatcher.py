"""Helpers for Home Assistant dispatcher & internal component/platform."""
from __future__ import annotations

from collections.abc import Callable, Coroutine
import logging
from typing import Any

from homeassistant.core import HassJob, HomeAssistant, callback
from homeassistant.loader import bind_hass
from homeassistant.util.async_ import run_callback_threadsafe
from homeassistant.util.logging import catch_log_exception

_LOGGER = logging.getLogger(__name__)
DATA_DISPATCHER = "dispatcher"


@bind_hass
def dispatcher_connect(
    hass: HomeAssistant, signal: str, target: Callable[..., None]
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
    hass: HomeAssistant, signal: str, target: Callable[..., Any]
) -> Callable[[], None]:
    """Connect a callable function to a signal.

    This method must be run in the event loop.
    """
    if DATA_DISPATCHER not in hass.data:
        hass.data[DATA_DISPATCHER] = {}
    hass.data[DATA_DISPATCHER].setdefault(signal, {})[target] = None

    @callback
    def async_remove_dispatcher() -> None:
        """Remove signal listener."""
        try:
            del hass.data[DATA_DISPATCHER][signal][target]
        except (KeyError, ValueError):
            # KeyError is key target listener did not exist
            # ValueError if listener did not exist within signal
            _LOGGER.warning("Unable to remove unknown dispatcher %s", target)

    return async_remove_dispatcher


@bind_hass
def dispatcher_send(hass: HomeAssistant, signal: str, *args: Any) -> None:
    """Send signal and data."""
    hass.loop.call_soon_threadsafe(async_dispatcher_send, hass, signal, *args)


def _generate_job(
    signal: str, target: Callable[..., Any]
) -> HassJob[..., None | Coroutine[Any, Any, None]]:
    """Generate a HassJob for a signal and target."""
    return HassJob(
        catch_log_exception(
            target,
            lambda *args: "Exception in {} when dispatching '{}': {}".format(
                # Functions wrapped in partial do not have a __name__
                getattr(target, "__name__", None) or str(target),
                signal,
                args,
            ),
        ),
        f"dispatcher {signal}",
    )


@callback
@bind_hass
def async_dispatcher_send(hass: HomeAssistant, signal: str, *args: Any) -> None:
    """Send signal and data.

    This method must be run in the event loop.
    """
    target_list: dict[
        Callable[..., Any], HassJob[..., None | Coroutine[Any, Any, None]] | None
    ] = hass.data.get(DATA_DISPATCHER, {}).get(signal, {})

    run: list[HassJob[..., None | Coroutine[Any, Any, None]]] = []
    for target, job in target_list.items():
        if job is None:
            job = _generate_job(signal, target)
            target_list[target] = job

        # Run the jobs all at the end
        # to ensure no jobs add more dispatchers
        # which can result in the target_list
        # changing size during iteration
        run.append(job)

    for job in run:
        hass.async_run_hass_job(job, *args)
