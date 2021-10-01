"""Trace support for automation."""
from __future__ import annotations

from contextlib import contextmanager
import logging
from typing import Any

from homeassistant.components.trace import (
    ActionTrace,
    async_store_trace,
    restore_traces as trace_restore_traces,
)
from homeassistant.components.trace.const import CONF_STORED_TRACES
from homeassistant.core import Context

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# mypy: allow-untyped-calls, allow-untyped-defs
# mypy: no-check-untyped-defs, no-warn-return-any


class AutomationTrace(ActionTrace):
    """Container for automation trace."""

    _domain = DOMAIN

    def __init__(
        self,
        item_id: str,
        config: dict[str, Any],
        blueprint_inputs: dict[str, Any],
        context: Context,
        run_id: None | str = None,
    ) -> None:
        """Container for automation trace."""
        super().__init__(item_id, config, blueprint_inputs, context, run_id)
        self._trigger_description: str | None = None

    def set_trigger_description(self, trigger: str) -> None:
        """Set trigger description."""
        self._trigger_description = trigger

    def as_short_dict(self) -> dict[str, Any]:
        """Return a brief dictionary version of this AutomationTrace."""
        result = super().as_short_dict()
        result["trigger"] = self._trigger_description
        return result

    @classmethod
    def from_dict(cls, data):
        """Restore from dict."""
        automation_trace = super().from_dict(data)
        automation_trace._trigger_description = (  # pylint: disable=protected-access
            data["trigger"]
        )
        return automation_trace


@contextmanager
def trace_automation(
    hass, automation_id, config, blueprint_inputs, context, trace_config
):
    """Trace action execution of automation with automation_id."""
    trace = AutomationTrace(automation_id, config, blueprint_inputs, context)
    async_store_trace(hass, trace, trace_config[CONF_STORED_TRACES])

    try:
        yield trace
    except Exception as ex:
        if automation_id:
            trace.set_error(ex)
        raise ex
    finally:
        if automation_id:
            trace.finished()


def restore_traces(hass):
    """Restore saved traces."""
    trace_restore_traces(hass, AutomationTrace, DOMAIN)
