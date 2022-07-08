"""Support for script and automation tracing and debugging."""
from __future__ import annotations

import abc
from collections import deque
import datetime as dt
import logging
from typing import Any

import voluptuous as vol

from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.json import ExtendedJSONEncoder
from homeassistant.helpers.storage import Store
from homeassistant.helpers.trace import (
    TraceElement,
    script_execution_get,
    trace_id_get,
    trace_id_set,
    trace_set_child_id,
)
from homeassistant.helpers.typing import ConfigType
import homeassistant.util.dt as dt_util
import homeassistant.util.uuid as uuid_util

from . import websocket_api
from .const import (
    CONF_STORED_TRACES,
    DATA_TRACE,
    DATA_TRACE_STORE,
    DATA_TRACES_RESTORED,
    DEFAULT_STORED_TRACES,
)
from .utils import LimitedSizeDict

_LOGGER = logging.getLogger(__name__)

DOMAIN = "trace"

STORAGE_KEY = "trace.saved_traces"
STORAGE_VERSION = 1

TRACE_CONFIG_SCHEMA = {
    vol.Optional(CONF_STORED_TRACES, default=DEFAULT_STORED_TRACES): cv.positive_int
}


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Initialize the trace integration."""
    hass.data[DATA_TRACE] = {}
    websocket_api.async_setup(hass)
    store = Store[dict[str, list]](
        hass, STORAGE_VERSION, STORAGE_KEY, encoder=ExtendedJSONEncoder
    )
    hass.data[DATA_TRACE_STORE] = store

    async def _async_store_traces_at_stop(*_) -> None:
        """Save traces to storage."""
        _LOGGER.debug("Storing traces")
        try:
            await store.async_save(
                {
                    key: list(traces.values())
                    for key, traces in hass.data[DATA_TRACE].items()
                }
            )
        except HomeAssistantError as exc:
            _LOGGER.error("Error storing traces", exc_info=exc)

    # Store traces when stopping hass
    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _async_store_traces_at_stop)

    return True


async def async_get_trace(hass, key, run_id):
    """Return the requested trace."""
    # Restore saved traces if not done
    await async_restore_traces(hass)

    return hass.data[DATA_TRACE][key][run_id].as_extended_dict()


async def async_list_contexts(hass, key):
    """List contexts for which we have traces."""
    # Restore saved traces if not done
    await async_restore_traces(hass)

    if key is not None:
        values = {key: hass.data[DATA_TRACE].get(key, {})}
    else:
        values = hass.data[DATA_TRACE]

    def _trace_id(run_id, key) -> dict:
        """Make trace_id for the response."""
        domain, item_id = key.split(".", 1)
        return {"run_id": run_id, "domain": domain, "item_id": item_id}

    return {
        trace.context.id: _trace_id(trace.run_id, key)
        for key, traces in values.items()
        for trace in traces.values()
    }


def _get_debug_traces(hass, key):
    """Return a serializable list of debug traces for a script or automation."""
    traces = []

    for trace in hass.data[DATA_TRACE].get(key, {}).values():
        traces.append(trace.as_short_dict())

    return traces


async def async_list_traces(hass, wanted_domain, wanted_key):
    """List traces for a domain."""
    # Restore saved traces if not done already
    await async_restore_traces(hass)

    if not wanted_key:
        traces = []
        for key in hass.data[DATA_TRACE]:
            domain = key.split(".", 1)[0]
            if domain == wanted_domain:
                traces.extend(_get_debug_traces(hass, key))
    else:
        traces = _get_debug_traces(hass, wanted_key)

    return traces


def async_store_trace(hass, trace, stored_traces):
    """Store a trace if its key is valid."""
    if key := trace.key:
        traces = hass.data[DATA_TRACE]
        if key not in traces:
            traces[key] = LimitedSizeDict(size_limit=stored_traces)
        else:
            traces[key].size_limit = stored_traces
        traces[key][trace.run_id] = trace


def _async_store_restored_trace(hass, trace):
    """Store a restored trace and move it to the end of the LimitedSizeDict."""
    key = trace.key
    traces = hass.data[DATA_TRACE]
    if key not in traces:
        traces[key] = LimitedSizeDict()
    traces[key][trace.run_id] = trace
    traces[key].move_to_end(trace.run_id, last=False)


async def async_restore_traces(hass):
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
        # Add stored traces in reversed order to priorize the newest traces
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
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Failed to restore trace")
                continue
            _async_store_restored_trace(hass, trace)


class BaseTrace(abc.ABC):
    """Base container for a script or automation trace."""

    context: Context
    key: str

    def as_dict(self) -> dict[str, Any]:
        """Return an dictionary version of this ActionTrace for saving."""
        return {
            "extended_dict": self.as_extended_dict(),
            "short_dict": self.as_short_dict(),
        }

    @abc.abstractmethod
    def as_extended_dict(self) -> dict[str, Any]:
        """Return an extended dictionary version of this ActionTrace."""

    @abc.abstractmethod
    def as_short_dict(self) -> dict[str, Any]:
        """Return a brief dictionary version of this ActionTrace."""


class ActionTrace(BaseTrace):
    """Base container for a script or automation trace."""

    _domain: str | None = None

    def __init__(
        self,
        item_id: str,
        config: dict[str, Any],
        blueprint_inputs: dict[str, Any],
        context: Context,
    ) -> None:
        """Container for script trace."""
        self._trace: dict[str, deque[TraceElement]] | None = None
        self._config: dict[str, Any] = config
        self._blueprint_inputs: dict[str, Any] = blueprint_inputs
        self.context: Context = context
        self._error: Exception | None = None
        self._state: str = "running"
        self._script_execution: str | None = None
        self.run_id: str = uuid_util.random_uuid_hex()
        self._timestamp_finish: dt.datetime | None = None
        self._timestamp_start: dt.datetime = dt_util.utcnow()
        self.key = f"{self._domain}.{item_id}"
        self._dict: dict[str, Any] | None = None
        self._short_dict: dict[str, Any] | None = None
        if trace_id_get():
            trace_set_child_id(self.key, self.run_id)
        trace_id_set((self.key, self.run_id))

    def set_trace(self, trace: dict[str, deque[TraceElement]]) -> None:
        """Set action trace."""
        self._trace = trace

    def set_error(self, ex: Exception) -> None:
        """Set error."""
        self._error = ex

    def finished(self) -> None:
        """Set finish time."""
        self._timestamp_finish = dt_util.utcnow()
        self._state = "stopped"
        self._script_execution = script_execution_get()

    def as_extended_dict(self) -> dict[str, Any]:
        """Return an extended dictionary version of this ActionTrace."""
        if self._dict:
            return self._dict

        result = dict(self.as_short_dict())

        traces = {}
        if self._trace:
            for key, trace_list in self._trace.items():
                traces[key] = [item.as_dict() for item in trace_list]

        result.update(
            {
                "trace": traces,
                "config": self._config,
                "blueprint_inputs": self._blueprint_inputs,
                "context": self.context,
            }
        )

        if self._state == "stopped":
            # Execution has stopped, save the result
            self._dict = result
        return result

    def as_short_dict(self) -> dict[str, Any]:
        """Return a brief dictionary version of this ActionTrace."""
        if self._short_dict:
            return self._short_dict

        last_step = None

        if self._trace:
            last_step = list(self._trace)[-1]
        domain, item_id = self.key.split(".", 1)

        result = {
            "last_step": last_step,
            "run_id": self.run_id,
            "state": self._state,
            "script_execution": self._script_execution,
            "timestamp": {
                "start": self._timestamp_start,
                "finish": self._timestamp_finish,
            },
            "domain": domain,
            "item_id": item_id,
        }
        if self._error is not None:
            result["error"] = str(self._error)

        if self._state == "stopped":
            # Execution has stopped, save the result
            self._short_dict = result
        return result


class RestoredTrace(BaseTrace):
    """Container for a restored script or automation trace."""

    def __init__(self, data: dict[str, Any]) -> None:
        """Restore from dict."""
        extended_dict = data["extended_dict"]
        short_dict = data["short_dict"]
        context = Context(
            user_id=extended_dict["context"]["user_id"],
            parent_id=extended_dict["context"]["parent_id"],
            id=extended_dict["context"]["id"],
        )
        self.context = context
        self.key = f"{extended_dict['domain']}.{extended_dict['item_id']}"
        self.run_id = extended_dict["run_id"]
        self._dict = extended_dict
        self._short_dict = short_dict

    def as_extended_dict(self) -> dict[str, Any]:
        """Return an extended dictionary version of this RestoredTrace."""
        return self._dict

    def as_short_dict(self) -> dict[str, Any]:
        """Return a brief dictionary version of this RestoredTrace."""
        return self._short_dict
