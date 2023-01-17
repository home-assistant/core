"""Config flow for the Open Thread Border Router integration."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.components.hassio import HassioServiceInfo
from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_URL
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN


class OTBRConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Home Assistant Sky Connect."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Set up by user."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        if user_input is not None:
            return self.async_create_entry(
                title="Thread",
                data={"url": user_input[CONF_URL]},
            )

        data_schema = vol.Schema({CONF_URL: str})
        return self.async_show_form(step_id="user", data_schema=data_schema)

    async def async_step_hassio(self, discovery_info: HassioServiceInfo) -> FlowResult:
        """Handle hassio discovery."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        config = discovery_info.config
        return self.async_create_entry(
            title="Thread",
            data={"url": f"http://{config['host']}:{config['port']}"},
        )
