"""Shared constants for script and automation tracing and debugging."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.util.hass_dict import HassKey

if TYPE_CHECKING:
    from homeassistant.helpers.storage import Store

    from .models import TraceData


CONF_STORED_TRACES = "stored_traces"
DATA_TRACE: HassKey[TraceData] = HassKey("trace")
DATA_TRACE_STORE: HassKey[Store[dict[str, list]]] = HassKey("trace_store")
DATA_TRACES_RESTORED: HassKey[bool] = HassKey("trace_traces_restored")
DEFAULT_STORED_TRACES = 5  # Stored traces per script or automation
