"""Support for automation and script tracing and debugging."""
from homeassistant.core import callback

from .const import DATA_TRACE


@callback
def get_debug_trace(hass, automation_id, run_id):
    """Return a serializable debug trace."""
    return hass.data[DATA_TRACE][automation_id][run_id]


@callback
def get_debug_traces_for_automation(hass, automation_id, summary=False):
    """Return a serializable list of debug traces for an automation."""
    traces = []

    for trace in hass.data[DATA_TRACE].get(automation_id, {}).values():
        if summary:
            traces.append(trace.as_short_dict())
        else:
            traces.append(trace.as_dict())

    return traces


@callback
def get_debug_traces(hass, summary=False):
    """Return a serializable list of debug traces."""
    traces = []

    for automation_id in hass.data[DATA_TRACE]:
        traces.extend(get_debug_traces_for_automation(hass, automation_id, summary))

    return traces
