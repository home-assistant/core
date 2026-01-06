"""Config flow for Volvo On Call integration."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

from .const import DOMAIN


class VolvoOnCallConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Volvo On Call."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""

        return self.async_abort(reason="deprecated")
