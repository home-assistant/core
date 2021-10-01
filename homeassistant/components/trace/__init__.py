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
        restored_traces = await store.async_load()
    except HomeAssistantError as exc:
        _LOGGER.error("Error loading traces", exc_info=exc)
        restored_traces = {}
    max_run_id = 0
    hass.data[DATA_RESTORED_TRACES] = defaultdict(dict)
    for key, traces in restored_traces.items():
        domain = key.split(".", 1)[0]
        hass.data[DATA_RESTORED_TRACES][domain][key] = traces
        for run_id in traces:
            max_run_id = max(int(run_id), max_run_id)
    ActionTrace._run_ids = count(max_run_id + 1)

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
    if key[1]:
        traces = hass.data[DATA_TRACE]
        if key not in traces:
            traces[key] = LimitedSizeDict(size_limit=stored_traces)
        else:
            traces[key].size_limit = stored_traces
        traces[key][trace.run_id] = trace


class ActionTrace:
    """Base container for a script or automation trace."""

    _domain: str | None = None
    _run_ids = None

    def __init__(
        self,
        item_id: str,
        config: dict[str, Any],
        blueprint_inputs: dict[str, Any],
        context: Context,
        run_id: None | str = None,
    ) -> None:
        """Container for script trace."""
        self._trace: dict[str, deque[TraceElement]] | None = None
        self._config: dict[str, Any] = config
        self._blueprint_inputs: dict[str, Any] = blueprint_inputs
        self.context: Context = context
        self._error: Exception | None = None
        self._state: str = "running"
        self._script_execution: str | None = None
        if run_id is None:
            assert self._run_ids
            self.run_id: str = str(next(self._run_ids))
        else:
            self.run_id = run_id
        self._timestamp_finish: dt.datetime | None = None
        self._timestamp_start: dt.datetime = dt_util.utcnow()
        self.key = f"{self._domain}.{item_id}"
        if trace_id_get():
            trace_set_child_id(self.key, self.run_id)
        trace_id_set((self.key, self.run_id))

    def set_trace(self, trace: dict[str, deque[TraceElement]]) -> None:
        """Set trace."""
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

        result = self.as_short_dict()

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

        return result

    def as_short_dict(self) -> dict[str, Any]:
        """Return a brief dictionary version of this ActionTrace."""

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

        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ActionTrace:
        """Restore from dict."""
        context = Context(
            user_id=data["context"]["user_id"],
            parent_id=data["context"]["parent_id"],
            id=data["context"]["id"],
        )
        actiontrace = cls(
            data["item_id"],
            data["config"],
            data["blueprint_inputs"],
            context,
            data["run_id"],
        )
        actiontrace._state = data["state"]
        actiontrace._script_execution = data["script_execution"]
        timestamps = data["timestamp"]
        if not (timestamp_start := dt_util.parse_datetime(timestamps["start"])):
            raise HomeAssistantError
        actiontrace._timestamp_start = timestamp_start
        if not (timestamp_finish := dt_util.parse_datetime(timestamps["finish"])):
            raise HomeAssistantError
        actiontrace._timestamp_finish = timestamp_finish
        if error := data.get("error"):
            actiontrace._error = error
        if trace := data.get("trace"):
            actiontrace._trace = {}
            for key, trace_list in trace.items():
                actiontrace._trace[key] = deque(
                    TraceElement.from_dict(item) for item in trace_list
                )
        return actiontrace
