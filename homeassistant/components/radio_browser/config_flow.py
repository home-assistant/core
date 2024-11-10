"""Config flow for Radio Browser integration."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

from .const import DOMAIN


class RadioBrowserConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Radio Browser."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if user_input is not None:
            return self.async_create_entry(title="Radio Browser", data={})

        return self.async_show_form(step_id="user")

    async def async_step_onboarding(
        self, data: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by onboarding."""
        return self.async_create_entry(title="Radio Browser", data={})
