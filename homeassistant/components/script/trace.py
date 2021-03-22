"""Trace support for script."""
from contextlib import contextmanager

from homeassistant.components.trace.const import DATA_TRACE, STORED_TRACES
from homeassistant.components.trace.utils import LimitedSizeDict
from homeassistant.helpers.trace import ActionTrace, trace_id_set


@contextmanager
def trace_script(hass, item_id, config, context):
    """Trace execution of a script."""
    key = ("script", item_id)
    trace = ActionTrace(key, config, context)
    trace_id_set((key, trace.run_id))

    if key:
        traces = hass.data[DATA_TRACE]
        if key not in traces:
            traces[key] = LimitedSizeDict(size_limit=STORED_TRACES)
        traces[key][trace.run_id] = trace

    try:
        yield trace
    except Exception as ex:  # pylint: disable=broad-except
        if key:
            trace.set_error(ex)
        raise ex
    finally:
        if key:
            trace.finished()
