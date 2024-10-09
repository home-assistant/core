"""Config flow for Home Assistant Supervisor integration."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

from .const import DOMAIN


class HassIoConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Home Assistant Supervisor."""

    VERSION = 1

    async def async_step_system(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        # We only need one Hass.io config entry
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        return self.async_create_entry(title="Supervisor", data={})
