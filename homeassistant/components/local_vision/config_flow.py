"""Config flow for Local vision."""

from typing import Any

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

from .const import DOMAIN


class LocalVisionConfigFlow(ConfigFlow, domain=DOMAIN):
    """Set up Local vision; there is nothing to configure."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm the setup."""
        if user_input is None:
            return self.async_show_form(step_id="user")
        return self.async_create_entry(title="Local vision", data={})
