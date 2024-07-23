"""Config flow to configure the Season integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_TYPE
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import DEFAULT_NAME, DOMAIN, TYPE_ASTRONOMICAL, TYPE_METEOROLOGICAL


class SeasonConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config flow for Season."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_TYPE])
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=DEFAULT_NAME,
                data={CONF_TYPE: user_input[CONF_TYPE]},
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_TYPE, default=TYPE_ASTRONOMICAL): SelectSelector(
                        SelectSelectorConfig(
                            translation_key="season_type",
                            mode=SelectSelectorMode.LIST,
                            options=[
                                TYPE_ASTRONOMICAL,
                                TYPE_METEOROLOGICAL,
                            ],
                        )
                    )
                },
            ),
        )
