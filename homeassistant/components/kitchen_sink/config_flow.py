"""Config flow to configure the Kitchen Sink component."""
from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

from . import DOMAIN


class KitchenSinkConfigFlow(ConfigFlow, domain=DOMAIN):
    """Kitchen Sink configuration flow."""

    VERSION = 1

    async def async_step_import(self, import_info: dict[str, Any]) -> ConfigFlowResult:
        """Set the config entry up from yaml."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        return self.async_create_entry(title="Kitchen Sink", data=import_info)
