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

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        eight = EightSleep(
            user_input[CONF_USERNAME],
            user_input[CONF_PASSWORD],
            self.hass.config.time_zone,
            async_get_clientsession(self.hass),
        )

        await self.async_set_unique_id(f"{DOMAIN}.{user_input[CONF_USERNAME]}")
        self._abort_if_unique_id_configured()
        try:
            await eight.fetch_token()
        except RequestError as err:
            if self.source == config_entries.SOURCE_USER:
                return self.async_show_form(
                    step_id="user",
                    data_schema=STEP_USER_DATA_SCHEMA,
                    errors={"base": "cannot_connect"},
                    description_placeholders={"error": str(err)},
                )

            _LOGGER.error(
                "Unable to import configuration.yaml configuration: %s", str(err)
            )
            return self.async_abort(
                reason="cannot_connect", description_placeholders={"error": str(err)}
            )
        else:
            return self.async_create_entry(
                title=user_input[CONF_USERNAME], data=user_input
            )

    async_step_import = async_step_user
