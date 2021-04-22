"""Trace support for script."""
from __future__ import annotations

from contextlib import contextmanager
from typing import Any

from homeassistant.components.trace import ActionTrace, async_store_trace
from homeassistant.core import Context


class ScriptTrace(ActionTrace):
    """Container for automation trace."""

    def __init__(
        self,
        item_id: str,
        config: dict[str, Any],
        context: Context,
    ):
        """Container for automation trace."""
        key = ("script", item_id)
        super().__init__(key, config, None, context)


@contextmanager
def trace_script(hass, item_id, config, context):
    """Trace execution of a script."""
    trace = ScriptTrace(item_id, config, context)
    async_store_trace(hass, trace)

    try:
        yield trace
    except Exception as ex:
        if item_id:
            trace.set_error(ex)
        raise ex
    finally:
        if item_id:
            trace.finished()
