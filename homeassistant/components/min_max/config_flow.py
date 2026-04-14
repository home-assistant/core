"""Config flow for Min/Max integration."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

from .const import DOMAIN


class MinMaxConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for min_max integration."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the user step."""
        return self.async_abort(reason="migrated_to_groups")
