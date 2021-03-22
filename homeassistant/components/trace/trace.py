"""Support for automation and script tracing and debugging."""
from homeassistant.core import callback

from .const import DATA_TRACE


@callback
def get_debug_trace(hass, key, run_id):
    """Return a serializable debug trace."""
    return hass.data[DATA_TRACE][key][run_id]


@callback
def get_debug_traces(hass, key, summary=False):
    """Return a serializable list of debug traces for an automation or script."""
    traces = []

    for trace in hass.data[DATA_TRACE].get(key, {}).values():
        if summary:
            traces.append(trace.as_short_dict())
        else:
            traces.append(trace.as_dict())

    return traces


@callback
def get_all_debug_traces(hass, summary=False):
    """Return a serializable list of debug traces for all automations and scripts."""
    traces = []

    for key in hass.data[DATA_TRACE]:
        traces.extend(get_debug_traces(hass, key, summary))

    return traces
