"""Config flow to connect with Home Assistant."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN


@config_entries.HANDLERS.register(DOMAIN)
class RecorderFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Recorder configuration flow."""

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)

    async def async_step_import(self, user_input: dict[str, Any]) -> FlowResult:
        """Import data."""
        # Only allow 1 instance.
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        return self.async_create_entry(
            title="Recorder",
            data=user_input,
        )
