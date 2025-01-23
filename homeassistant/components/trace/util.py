"""Support for script and automation tracing and debugging."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util.limited_size_dict import LimitedSizeDict

from .const import DATA_TRACE, DATA_TRACE_STORE, DATA_TRACES_RESTORED
from .models import ActionTrace, BaseTrace, RestoredTrace, TraceData

_LOGGER = logging.getLogger(__name__)


async def async_get_trace(
    hass: HomeAssistant, key: str, run_id: str
) -> dict[str, BaseTrace]:
    """Return the requested trace."""
    # Restore saved traces if not done
    await async_restore_traces(hass)

    return hass.data[DATA_TRACE][key][run_id].as_extended_dict()


async def async_list_contexts(
    hass: HomeAssistant, key: str | None
) -> dict[str, dict[str, str]]:
    """List contexts for which we have traces."""
    # Restore saved traces if not done
    await async_restore_traces(hass)

    values: Mapping[str, LimitedSizeDict[str, BaseTrace] | None] | TraceData
    if key is not None:
        values = {key: hass.data[DATA_TRACE].get(key)}
    else:
        values = hass.data[DATA_TRACE]

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
    if traces_for_key := hass.data[DATA_TRACE].get(key):
        return [trace.as_short_dict() for trace in traces_for_key.values()]
    return []


async def async_list_traces(
    hass: HomeAssistant, wanted_domain: str, wanted_key: str | None
) -> list[dict[str, Any]]:
    """List traces for a domain."""
    # Restore saved traces if not done already
    await async_restore_traces(hass)

    if not wanted_key:
        traces: list[dict[str, Any]] = []
        for key in hass.data[DATA_TRACE]:
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
        traces = hass.data[DATA_TRACE]
        if key not in traces:
            traces[key] = LimitedSizeDict(size_limit=stored_traces)
        else:
            traces[key].size_limit = stored_traces
        traces[key][trace.run_id] = trace


def _async_store_restored_trace(hass: HomeAssistant, trace: RestoredTrace) -> None:
    """Store a restored trace and move it to the end of the LimitedSizeDict."""
    key = trace.key
    traces = hass.data[DATA_TRACE]
    if key not in traces:
        traces[key] = LimitedSizeDict()
    traces[key][trace.run_id] = trace
    traces[key].move_to_end(trace.run_id, last=False)


async def async_restore_traces(hass: HomeAssistant) -> None:
    """Restore saved traces."""
    if DATA_TRACES_RESTORED in hass.data:
        return

    hass.data[DATA_TRACES_RESTORED] = True

    store = hass.data[DATA_TRACE_STORE]
    try:
        restored_traces = await store.async_load() or {}
    except HomeAssistantError:
        _LOGGER.exception("Error loading traces")
        restored_traces = {}

    for key, traces in restored_traces.items():
        # Add stored traces in reversed order to prioritize the newest traces
        for json_trace in reversed(traces):
            if (
                (stored_traces := hass.data[DATA_TRACE].get(key))
                and stored_traces.size_limit is not None
                and len(stored_traces) >= stored_traces.size_limit
            ):
                break

            try:
                trace = RestoredTrace(json_trace)
            # Catch any exception to not blow up if the stored trace is invalid
            except Exception:
                _LOGGER.exception("Failed to restore trace")
                continue
            _async_store_restored_trace(hass, trace)
