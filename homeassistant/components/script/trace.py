"""Trace support for script."""
from __future__ import annotations

from contextlib import contextmanager

from homeassistant.components.trace import ScriptTrace, async_store_trace


@contextmanager
def trace_script(hass, item_id, config, context):
    """Trace execution of a script."""
    trace = ScriptTrace(item_id, config, context)
    async_store_trace(hass, trace)

    try:
        yield trace
    except Exception as ex:  # pylint: disable=broad-except
        if item_id:
            trace.set_error(ex)
        raise ex
    finally:
        if item_id:
            trace.finished()
