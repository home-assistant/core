"""Trace support for script."""
from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator

from homeassistant.components.trace import ActionTrace, async_store_trace
from homeassistant.components.trace.const import CONF_STORED_TRACES
from homeassistant.core import Context, HomeAssistant


class ScriptTrace(ActionTrace):
    """Container for automation trace."""

    def __init__(
        self,
        item_id: str,
        config: dict[str, Any],
        blueprint_inputs: dict[str, Any],
        context: Context,
    ):
        """Container for automation trace."""
        key = ("script", item_id)
        super().__init__(key, config, blueprint_inputs, context)


@contextmanager
def trace_script(
    hass: HomeAssistant,
    item_id: str,
    config: dict[str, Any],
    blueprint_inputs: dict[str, Any],
    context: Context,
    trace_config: dict[str, Any],
) -> Iterator[ScriptTrace]:
    """Trace execution of a script."""
    trace = ScriptTrace(item_id, config, blueprint_inputs, context)
    async_store_trace(hass, trace, trace_config[CONF_STORED_TRACES])

    try:
        yield trace
    except Exception as ex:
        if item_id:
            trace.set_error(ex)
        raise ex
    finally:
        if item_id:
            trace.finished()
