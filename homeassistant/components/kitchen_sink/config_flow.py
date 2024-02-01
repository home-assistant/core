"""Config flow to configure the Kitchen Sink component."""
from __future__ import annotations

from typing import Any

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from . import DOMAIN


class KitchenSinkConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Kitchen Sink configuration flow."""

    VERSION = 1

    async def async_step_import(self, import_info: dict[str, Any]) -> FlowResult:
        """Set the config entry up from yaml."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        return self.async_create_entry(title="Kitchen Sink", data=import_info)

    async def async_step_reauth(self, data):
        """Reauth step."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None):
        """Reauth confirm step."""
        if user_input is None:
            return self.async_show_form(step_id="reauth_confirm")
        return self.async_abort(reason="reauth_successful")
