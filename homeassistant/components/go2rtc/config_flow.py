"""Config flow for the go2rtc integration."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

from .const import DOMAIN


class CloudConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for the go2rtc integration."""

    VERSION = 1

    async def async_step_system(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the system step."""
        return self.async_create_entry(title="go2rtc", data={})
