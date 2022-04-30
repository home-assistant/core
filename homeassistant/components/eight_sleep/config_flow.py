"""Config flow for Eight Sleep integration."""
from __future__ import annotations

import asyncio
from typing import Any

from pyeight.eight import EightSleep
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

        # We use a fresh session so that we don't have any API weirdness
        eight = EightSleep(
            user_input[CONF_USERNAME],
            user_input[CONF_PASSWORD],
            self.hass.config.time_zone,
            async_get_clientsession(self.hass),
        )

        await eight.fetch_token()
        if eight.token:
            await eight.fetch_device_list()
            await self.async_set_unique_id(eight.deviceid)
            self._abort_if_unique_id_configured()
            # Due to Eight Sleep's aggressive rate limiting and a lack of good handling
            # in the library, we have to wait 5 seconds before we can create the entry
            # since it will trigger new API calls
            await asyncio.sleep(5)
            return self.async_create_entry(
                title=user_input[CONF_USERNAME], data=user_input
            )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors={"base": "invalid_auth"},
        )

    async_step_import = async_step_user
