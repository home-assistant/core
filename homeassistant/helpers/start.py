"""Helpers to help during startup."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import Any

from homeassistant.const import EVENT_HOMEASSISTANT_START, EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import (
    CALLBACK_TYPE,
    CoreState,
    Event,
    HassJob,
    HomeAssistant,
    callback,
)
from homeassistant.util.event_type import EventType

from .typing import NoEventData


@callback
def _async_at_core_state(
    hass: HomeAssistant,
    at_start_cb: Callable[[HomeAssistant], Coroutine[Any, Any, None] | None],
    event_type: EventType[NoEventData],
    check_state: Callable[[HomeAssistant], bool],
) -> CALLBACK_TYPE:
    """Execute a job at_start_cb when Home Assistant has the wanted state.

    The job is executed immediately if Home Assistant is in the wanted state.
    Will wait for event specified by event_type if it isn't.
    """
    at_start_job = HassJob(at_start_cb)
    if check_state(hass):
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

    unsub = hass.bus.async_listen_once(event_type, _matched_event)
    return cancel


@callback
def async_at_start(
    hass: HomeAssistant,
    at_start_cb: Callable[[HomeAssistant], Coroutine[Any, Any, None] | None],
) -> CALLBACK_TYPE:
    """Execute a job at_start_cb when Home Assistant is starting.

    The job is executed immediately if Home Assistant is already starting or started.
    Will wait for EVENT_HOMEASSISTANT_START if it isn't.
    """

    def _is_running(hass: HomeAssistant) -> bool:
        return hass.is_running

    return _async_at_core_state(
        hass, at_start_cb, EVENT_HOMEASSISTANT_START, _is_running
    )


@callback
def async_at_started(
    hass: HomeAssistant,
    at_start_cb: Callable[[HomeAssistant], Coroutine[Any, Any, None] | None],
) -> CALLBACK_TYPE:
    """Execute a job at_start_cb when Home Assistant has started.

    The job is executed immediately if Home Assistant is already started.
    Will wait for EVENT_HOMEASSISTANT_STARTED if it isn't.
    """

    def _is_started(hass: HomeAssistant) -> bool:
        return hass.state is CoreState.running

    return _async_at_core_state(
        hass, at_start_cb, EVENT_HOMEASSISTANT_STARTED, _is_started
    )
