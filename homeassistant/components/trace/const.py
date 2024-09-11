"""Shared constants for script and automation tracing and debugging."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.util.hass_dict import HassKey

if TYPE_CHECKING:
    from . import TraceData

DOMAIN = "trace"

CONF_STORED_TRACES = "stored_traces"
DATA_TRACE: HassKey[TraceData] = HassKey(DOMAIN)
DATA_TRACE_STORE = "trace_store"
DATA_TRACES_RESTORED = "trace_traces_restored"
DEFAULT_STORED_TRACES = 5  # Stored traces per script or automation
