"""PurpleAir options flow."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_SHOW_ON_MAP

from .const import CONF_SETTINGS


class PurpleAirOptionsFlow(OptionsFlow):
    """Options flow."""

    def __init__(self) -> None:
        """Initialize."""
        self._flow_data: dict[str, Any] = {}

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle user initialization flow."""
        return await self.async_step_settings()

    @property
    def settings_schema(self) -> vol.Schema:
        """Settings schema."""
        return vol.Schema(
            {
                vol.Optional(
                    CONF_SHOW_ON_MAP,
                    default=self.config_entry.options.get(CONF_SHOW_ON_MAP, False),
                ): bool
            }
        )

    async def async_step_settings(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle settings flow."""
        if user_input is None:
            return self.async_show_form(
                step_id=CONF_SETTINGS, data_schema=self.settings_schema
            )

        options = deepcopy(dict(self.config_entry.options))
        options[CONF_SHOW_ON_MAP] = user_input.get(CONF_SHOW_ON_MAP, False)

        return self.async_create_entry(data=options)
