"""Config flow for WittIOT integration."""
from __future__ import annotations

import logging

import voluptuous as vol
from wittiot import API
from wittiot.errors import WittiotError

from homeassistant import config_entries
from homeassistant.helpers import aiohttp_client

from .const import CONF_IP, CONNECTION_TYPE, DEVICE_NAME, DOMAIN, LOCAL

_LOGGER = logging.getLogger(__name__)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for WittIOT."""

    async def async_step_user(self, user_input=None):
        """Handle the local step."""
        errors = {}
        data_schema = vol.Schema({vol.Required(CONF_IP): str})

        if user_input is not None:
            ip = user_input[CONF_IP].replace(" ", "")

            api = API(ip, session=aiohttp_client.async_get_clientsession(self.hass))

            try:
                devices = await api.request_loc_info()
            except WittiotError:
                errors["base"] = "cannot_connect"
            _LOGGER.debug("New data received: %s", devices)

            if not devices:
                errors["base"] = "cannot_connect"

            if not errors:
                unique_id = devices["dev_name"]
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=unique_id,
                    data={
                        DEVICE_NAME: unique_id,
                        CONF_IP: ip,
                        CONNECTION_TYPE: LOCAL,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )
