"""Adds config flow for Tibber integration."""
import asyncio

import aiohttp
import tibber
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

DATA_SCHEMA = vol.Schema({vol.Required(CONF_ACCESS_TOKEN): str})


class TibberConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Tibber integration."""

    VERSION = 1

    async def async_step_import(self, import_info):
        """Set the config entry up from yaml."""
        return await self.async_step_user(import_info)

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""

        if self._async_current_entries():
            return self.async_abort(reason="already_configured")

        if user_input is not None:
            access_token = user_input[CONF_ACCESS_TOKEN].replace(" ", "")

            tibber_connection = tibber.Tibber(
                access_token=access_token,
                websession=async_get_clientsession(self.hass),
            )

            errors = {}

            try:
                await tibber_connection.update_info()
            except asyncio.TimeoutError:
                errors[CONF_ACCESS_TOKEN] = "timeout"
            except aiohttp.ClientError:
                errors[CONF_ACCESS_TOKEN] = "cannot_connect"
            except tibber.InvalidLogin:
                errors[CONF_ACCESS_TOKEN] = "invalid_access_token"

            if errors:
                return self.async_show_form(
                    step_id="user",
                    data_schema=DATA_SCHEMA,
                    errors=errors,
                )

            unique_id = tibber_connection.user_id
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=tibber_connection.name,
                data={CONF_ACCESS_TOKEN: access_token},
            )

        return self.async_show_form(
            step_id="user",
            data_schema=DATA_SCHEMA,
            errors={},
        )
