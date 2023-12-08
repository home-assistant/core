"""Trace support for script."""
from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from homeassistant.components.trace import (
    CONF_STORED_TRACES,
    ActionTrace,
    async_store_trace,
)
from homeassistant.core import Context, HomeAssistant

from .const import DOMAIN


class ScriptTrace(ActionTrace):
    """Container for script trace."""

    _domain = DOMAIN


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
