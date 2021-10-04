"""Support for script and automation tracing and debugging."""
from __future__ import annotations

from collections import defaultdict, deque
import datetime as dt
from itertools import count
import logging
from typing import Any

import voluptuous as vol

from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Context
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
import homeassistant.util.dt as dt_util

from . import websocket_api
from .const import (
    CONF_STORED_TRACES,
    DATA_RESTORED_TRACES,
    DATA_TRACE,
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


async def async_setup(hass, config):
    """Initialize the trace integration."""
    hass.data[DATA_TRACE] = {}
    websocket_api.async_setup(hass)
    store = Store(hass, STORAGE_VERSION, STORAGE_KEY, encoder=ExtendedJSONEncoder)
    _LOGGER.debug("Loading traces")
    try:
        restored_traces = await store.async_load() or {}
    except HomeAssistantError as exc:
        _LOGGER.error("Error loading traces", exc_info=exc)
        restored_traces = {}
    max_run_id = 0
    hass.data[DATA_RESTORED_TRACES] = defaultdict(dict)
    for key, traces in restored_traces.items():
        domain = key.split(".", 1)[0]
        hass.data[DATA_RESTORED_TRACES][domain][key] = traces
        for run_id in traces:
            max_run_id = max(int(run_id) + 1, max_run_id)
    ActionTrace._run_ids = count(max_run_id)  # pylint: disable=protected-access

    async def _async_store_traces_at_stop(*_) -> None:
        """Save traces to storage."""
        _LOGGER.debug("Storing traces")
        try:
            await store.async_save(hass.data[DATA_TRACE])
        except HomeAssistantError as exc:
            _LOGGER.error("Error saving traces", exc_info=exc)

    # Store traces when stopping hass
    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _async_store_traces_at_stop)

    return True


def async_store_trace(hass, trace, stored_traces):
    """Store a trace if its item_id is valid."""
    key = trace.key
    if key:
        traces = hass.data[DATA_TRACE]
        if key not in traces:
            traces[key] = LimitedSizeDict(size_limit=stored_traces)
        else:
            traces[key].size_limit = stored_traces
        traces[key][trace.run_id] = trace


def restore_traces(hass, cls, domain):
    """Restore saved traces."""
    restored_traces = hass.data[DATA_RESTORED_TRACES].pop(domain, {})
    for traces in restored_traces.values():
        for json_trace in traces.values():
            try:
                trace = cls.from_dict(json_trace)
                async_store_trace(hass, trace, None)
            # Catch any exception to not blow up if the stored trace is invalid
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Failed to restore trace")


class ActionTrace:
    """Base container for a script or automation trace."""

    _domain: str | None = None
    _run_ids = None

    def __init__(self, item_id: str) -> None:
        """Container for script trace."""
        self._trace: dict[str, deque[TraceElement]] | None = None
        self._config: dict[str, Any] | None = None
        self._blueprint_inputs: dict[str, Any] | None = None
        self.context: Context | None = None
        self._error: Exception | None = None
        self._state: str = "stopped"
        self._script_execution: str | None = None
        self.run_id: str = "unknown"
        self._timestamp_finish: dt.datetime | None = None
        self._timestamp_start: dt.datetime | None = None
        self.key = f"{self._domain}.{item_id}"
        self._dict: dict[str, Any] | None = None
        self._short_dict: dict[str, Any] | None = None

    def set_basic_info(
        self, config: dict[str, Any], blueprint_inputs: dict[str, Any], context: Context
    ) -> None:
        """Set basic information for tracing, not called for restored traces."""
        self._config = config
        self._blueprint_inputs = blueprint_inputs
        self.context = context
        self._state = "running"
        assert self._run_ids
        self.run_id = str(next(self._run_ids))
        self._timestamp_start = dt_util.utcnow()
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

    def as_dict(self) -> dict[str, Any]:
        """Return dictionary version of this ActionTrace."""

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

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ActionTrace:
        """Restore from dict."""
        actiontrace = cls(data["item_id"])
        actiontrace.run_id = data["run_id"]
        actiontrace._dict = data
        actiontrace._short_dict = {
            "last_step": data["last_step"],
            "run_id": data["run_id"],
            "state": data["state"],
            "script_execution": data["script_execution"],
            "timestamp": data["timestamp"],
            "domain": data["domain"],
            "item_id": data["item_id"],
        }
        if "error" in data:
            actiontrace._short_dict["error"] = data["error"]
        if "last_step" in data:
            actiontrace._short_dict["last_step"] = data["last_step"]
        return actiontrace
