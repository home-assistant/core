"""Config flow for Wittiot integration."""
from __future__ import annotations

import logging

import voluptuous as vol
from wittiot import API
from wittiot.errors import WittiotError

from homeassistant import config_entries, exceptions
from homeassistant.helpers import aiohttp_client

from .const import CONF_IP, CONNECTION_TYPE, DOMAIN, LOCAL

_LOGGER = logging.getLogger(__name__)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Wittiot."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the local step."""
        data_schema = vol.Schema({vol.Required(CONF_IP): str})
        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=data_schema,
            )

        ip = user_input[CONF_IP].replace(" ", "")

        session = aiohttp_client.async_get_clientsession(self.hass)
        api = API(ip, session=session)

        try:
            devices = await api.request_loc_info()
            _LOGGER.info("New data received: %s", devices)
        except WittiotError:
            return self.async_show_form(
                step_id="user",
                data_schema=data_schema,
                errors={"base": "cannot_connect"},
            )

        if not devices:
            return self.async_show_form(
                step_id="user",
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


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidHost(exceptions.HomeAssistantError):
    """Error to indicate there is an invalid hostname."""
