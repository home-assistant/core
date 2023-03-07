"""Config flow for the Pioneer AVR component."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT, CONF_TIMEOUT
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import (
    CONF_SOURCES,
    CONF_ZONES,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DEFAULT_SOURCES,
    DEFAULT_TIMEOUT,
    DEFAULT_ZONE,
    DOMAIN,
)

apps_list = {k: f"{v} ({k})" if v else k for k, v in DEFAULT_SOURCES.items()}
apps = [SelectOptionDict(value="sources", label="Add source")] + [
    SelectOptionDict(value=k, label=v) for k, v in apps_list.items()
]

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int,
        vol.Optional(CONF_SOURCES): SelectSelector(
            SelectSelectorConfig(
                options=apps,
                mode=SelectSelectorMode.DROPDOWN,
                multiple=True,
            )
        ),
        vol.Optional(CONF_ZONES, default=DEFAULT_ZONE): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=2)
        ),
    }
)


class PioneerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Pioneer config flow."""

    VERSION = 1

    async def async_step_import(self, import_config: dict[str, Any]) -> FlowResult:
        """Import a config entry from configuration.yaml."""

        self._async_abort_entries_match({CONF_HOST: import_config[CONF_HOST]})
        return self.async_create_entry(
            title=import_config[CONF_NAME] or DEFAULT_NAME,
            data=import_config,
        )

    async def async_step_user(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Handle the user setup step."""
        if user_input is not None:
            self._async_abort_entries_match({CONF_HOST: user_input[CONF_HOST]})

            return self.async_create_entry(
                title=DEFAULT_NAME,
                data=user_input,
            )

        data_schema = self.add_suggested_values_to_schema(DATA_SCHEMA, user_input)
        return self.async_show_form(step_id="user", data_schema=data_schema)
