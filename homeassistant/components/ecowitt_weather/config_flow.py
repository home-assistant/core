"""Config flow for Ecowitt Weather integration."""
from __future__ import annotations

import logging
from typing import Any

from ecpat1 import API
from ecpat1.errors import EcowittError
import voluptuous as vol

from homeassistant import config_entries, exceptions
from homeassistant.const import CONF_API_KEY
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import aiohttp_client

from .const import (
    CLOUD,
    CONF_APP_KEY,
    CONF_IP,
    CONF_MAC,
    CONNECTION_TYPE,
    DOMAIN,
    LOCAL,
)

_LOGGER = logging.getLogger(__name__)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Ecowitt Weather."""

    VERSION = 2

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        data_schema = vol.Schema(
            {
                vol.Required(CONNECTION_TYPE, default=CLOUD): vol.In(
                    (
                        CLOUD,
                        LOCAL,
                    )
                )
            }
        )

        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=data_schema,
            )

        if user_input[CONNECTION_TYPE] == LOCAL:
            return await self.async_step_local()
        return await self.async_step_cloud()

    async def async_step_local(self, user_input=None):
        """Handle the local step."""
        data_schema = vol.Schema({vol.Required(CONF_IP): str})
        if user_input is None:
            return self.async_show_form(
                step_id="local",
                data_schema=data_schema,
            )

        ip = user_input[CONF_IP].replace(" ", "")

        session = aiohttp_client.async_get_clientsession(self.hass)
        api = API("", "", ip, session=session)

        try:
            devices = await api.request_loc_info()
            _LOGGER.info("New data received: %s", devices)
        except EcowittError:
            return self.async_show_form(
                step_id="local",
                data_schema=data_schema,
                errors={"base": "cannot_connect"},
            )

        if not devices:
            return self.async_show_form(
                step_id="local",
                data_schema=data_schema,
                errors={"base": "cannot_connect"},
            )

        unique_id = ip
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=unique_id,
            data={
                CONF_IP: ip,
                CONNECTION_TYPE: LOCAL,
            },
        )

    async def async_step_cloud(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the cloud step."""
        data_schema = vol.Schema(
            {
                vol.Required(CONF_API_KEY): str,
                vol.Required(CONF_APP_KEY): str,
                vol.Required(CONF_MAC): str,
            }
        )
        if user_input is None:
            return self.async_show_form(step_id="cloud", data_schema=data_schema)

        errors: dict[str, str] = {}

        await self.async_set_unique_id(user_input[CONF_APP_KEY])
        self._abort_if_unique_id_configured()

        session = aiohttp_client.async_get_clientsession(self.hass)
        api = API(
            user_input[CONF_APP_KEY], user_input[CONF_API_KEY], "", session=session
        )

        try:
            # devices = await api.get_devices()
            devices = await api.get_data_real_time(user_input[CONF_MAC])
            _LOGGER.info("New data received: %s", devices)
        except EcowittError:
            return self.async_show_form(
                step_id="cloud",
                data_schema=data_schema,
                errors=errors,
            )

        if not devices:
            return self.async_show_form(
                step_id="cloud",
                data_schema=data_schema,
                errors=errors,
            )

        return self.async_create_entry(
            title=user_input[CONF_MAC],
            data={
                CONF_APP_KEY: user_input[CONF_APP_KEY],
                CONF_API_KEY: user_input[CONF_API_KEY],
                CONF_MAC: user_input[CONF_MAC],
                CONNECTION_TYPE: CLOUD,
            },
        )


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidHost(exceptions.HomeAssistantError):
    """Error to indicate there is an invalid hostname."""
