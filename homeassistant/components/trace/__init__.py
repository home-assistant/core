"""Support for script and automation tracing and debugging."""
from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

import voluptuous as vol

from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.json import ExtendedJSONEncoder
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import ConfigType
from homeassistant.util.limited_size_dict import LimitedSizeDict

from . import websocket_api
from .const import (
    CONF_STORED_TRACES,
    DATA_TRACE,
    DATA_TRACE_STORE,
    DATA_TRACES_RESTORED,
    DEFAULT_STORED_TRACES,
)
from .models import ActionTrace, BaseTrace, RestoredTrace

_LOGGER = logging.getLogger(__name__)

DOMAIN = "trace"

STORAGE_KEY = "trace.saved_traces"
STORAGE_VERSION = 1

TRACE_CONFIG_SCHEMA = {
    vol.Optional(CONF_STORED_TRACES, default=DEFAULT_STORED_TRACES): cv.positive_int
}

TraceData = dict[str, LimitedSizeDict[str, BaseTrace]]


@callback
def _get_data(hass: HomeAssistant) -> TraceData:
    return hass.data[DATA_TRACE]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Initialize the trace integration."""
    hass.data[DATA_TRACE] = {}
    websocket_api.async_setup(hass)
    store = Store[dict[str, list]](
        hass, STORAGE_VERSION, STORAGE_KEY, encoder=ExtendedJSONEncoder
    )
    hass.data[DATA_TRACE_STORE] = store

    async def _async_store_traces_at_stop(_: Event) -> None:
        """Save traces to storage."""
        _LOGGER.debug("Storing traces")
        try:
            await store.async_save(
                {key: list(traces.values()) for key, traces in _get_data(hass).items()}
            )
        except HomeAssistantError as exc:
            _LOGGER.error("Error storing traces", exc_info=exc)

    # Store traces when stopping hass
    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _async_store_traces_at_stop)

    return True


async def async_get_trace(
    hass: HomeAssistant, key: str, run_id: str
) -> dict[str, BaseTrace]:
    """Return the requested trace."""
    # Restore saved traces if not done
    await async_restore_traces(hass)

    return _get_data(hass)[key][run_id].as_extended_dict()


async def async_list_contexts(
    hass: HomeAssistant, key: str | None
) -> dict[str, dict[str, str]]:
    """List contexts for which we have traces."""
    # Restore saved traces if not done
    await async_restore_traces(hass)

    values: Mapping[str, LimitedSizeDict[str, BaseTrace] | None]
    if key is not None:
        values = {key: _get_data(hass).get(key)}
    else:
        values = _get_data(hass)

    def _trace_id(run_id: str, key: str) -> dict[str, str]:
        """Make trace_id for the response."""
        domain, item_id = key.split(".", 1)
        return {"run_id": run_id, "domain": domain, "item_id": item_id}

    return {
        trace.context.id: _trace_id(trace.run_id, key)
        for key, traces in values.items()
        if traces is not None
        for trace in traces.values()
    }


def _get_debug_traces(hass: HomeAssistant, key: str) -> list[dict[str, Any]]:
    """Return a serializable list of debug traces for a script or automation."""
    traces: list[dict[str, Any]] = []

    if traces_for_key := _get_data(hass).get(key):
        for trace in traces_for_key.values():
            traces.append(trace.as_short_dict())

    return traces


async def async_list_traces(
    hass: HomeAssistant, wanted_domain: str, wanted_key: str | None
) -> list[dict[str, Any]]:
    """List traces for a domain."""
    # Restore saved traces if not done already
    await async_restore_traces(hass)

    if not wanted_key:
        traces: list[dict[str, Any]] = []
        for key in _get_data(hass):
            domain = key.split(".", 1)[0]
            if domain == wanted_domain:
                traces.extend(_get_debug_traces(hass, key))
    else:
        traces = _get_debug_traces(hass, wanted_key)

    return traces


def async_store_trace(
    hass: HomeAssistant, trace: ActionTrace, stored_traces: int
) -> None:
    """Store a trace if its key is valid."""
    if key := trace.key:
        traces = _get_data(hass)
        if key not in traces:
            traces[key] = LimitedSizeDict(size_limit=stored_traces)
        else:
            traces[key].size_limit = stored_traces
        traces[key][trace.run_id] = trace


def _async_store_restored_trace(hass: HomeAssistant, trace: RestoredTrace) -> None:
    """Store a restored trace and move it to the end of the LimitedSizeDict."""
    key = trace.key
    traces = _get_data(hass)
    if key not in traces:
        traces[key] = LimitedSizeDict()
    traces[key][trace.run_id] = trace
    traces[key].move_to_end(trace.run_id, last=False)


async def async_restore_traces(hass: HomeAssistant) -> None:
    """Restore saved traces."""
    if DATA_TRACES_RESTORED in hass.data:
        return

    hass.data[DATA_TRACES_RESTORED] = True

    store: Store[dict[str, list]] = hass.data[DATA_TRACE_STORE]
    try:
        restored_traces = await store.async_load() or {}
    except HomeAssistantError:
        _LOGGER.exception("Error loading traces")
        restored_traces = {}

    for key, traces in restored_traces.items():
        # Add stored traces in reversed order to priorize the newest traces
        for json_trace in reversed(traces):
            if (
                (stored_traces := _get_data(hass).get(key))
                and stored_traces.size_limit is not None
                and len(stored_traces) >= stored_traces.size_limit
            ):
                break

            try:
                trace = RestoredTrace(json_trace)
            # Catch any exception to not blow up if the stored trace is invalid
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Failed to restore trace")
                continue
            _async_store_restored_trace(hass, trace)
