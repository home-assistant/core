"""Config flow for Eight Sleep integration."""
from __future__ import annotations

import logging
from typing import Any

from pyeight.eight import EightSleep
from pyeight.exceptions import RequestError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): TextSelector(
            TextSelectorConfig(type=TextSelectorType.EMAIL)
        ),
        vol.Required(CONF_PASSWORD): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD)
        ),
    }
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Eight Sleep."""

    VERSION = 1

    async def _validate_data(self, config: dict[str, str]) -> str | None:
        """Validate input data and return any error."""
        await self.async_set_unique_id(config[CONF_USERNAME].lower())
        self._abort_if_unique_id_configured()

        eight = EightSleep(
            config[CONF_USERNAME],
            config[CONF_PASSWORD],
            self.hass.config.time_zone,
            client_session=async_get_clientsession(self.hass),
        )

        try:
            await eight.fetch_token()
        except RequestError as err:
            return str(err)

        return None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        if (err := await self._validate_data(user_input)) is not None:
            return self.async_show_form(
                step_id="user",
                data_schema=STEP_USER_DATA_SCHEMA,
                errors={"base": "cannot_connect"},
                description_placeholders={"error": err},
            )

        return self.async_create_entry(title=user_input[CONF_USERNAME], data=user_input)

    async def async_step_import(self, import_config: dict) -> FlowResult:
        """Handle import."""
        if (err := await self._validate_data(import_config)) is not None:
            _LOGGER.error("Unable to import configuration.yaml configuration: %s", err)
            return self.async_abort(
                reason="cannot_connect", description_placeholders={"error": err}
            )

        return self.async_create_entry(
            title=import_config[CONF_USERNAME], data=import_config
        )
