"""Trace support for automation."""
from __future__ import annotations

from contextlib import contextmanager

from homeassistant.components.trace import AutomationTrace, async_store_trace

# mypy: allow-untyped-calls, allow-untyped-defs
# mypy: no-check-untyped-defs, no-warn-return-any


@contextmanager
def trace_automation(hass, item_id, config, context):
    """Trace action execution of automation with item_id."""
    trace = AutomationTrace(item_id, config, context)
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
