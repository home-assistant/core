"""Helpers to help during startup."""
from __future__ import annotations

from collections.abc import Awaitable, Callable

from homeassistant.const import EVENT_HOMEASSISTANT_START
from homeassistant.core import CALLBACK_TYPE, Event, HassJob, HomeAssistant, callback


@callback
def async_at_start(
    hass: HomeAssistant, at_start_cb: Callable[[HomeAssistant], Awaitable[None] | None]
) -> CALLBACK_TYPE:
    """Execute something when Home Assistant is started.

    Will execute it now if Home Assistant is already started.
    """
    at_start_job = HassJob(at_start_cb)
    if hass.is_running:
        hass.async_run_hass_job(at_start_job, hass)
        return lambda: None

    unsub: None | CALLBACK_TYPE = None

    @callback
    def _matched_event(event: Event) -> None:
        """Call the callback when Home Assistant started."""
        hass.async_run_hass_job(at_start_job, hass)
        nonlocal unsub
        unsub = None

    @callback
    def cancel() -> None:
        if unsub:
            unsub()

    unsub = hass.bus.async_listen_once(EVENT_HOMEASSISTANT_START, _matched_event)
    return cancel
