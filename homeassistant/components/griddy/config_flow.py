"""Config flow for Griddy Power integration."""
import asyncio
import logging

from aiohttp import ClientError
from griddypower.async_api import LOAD_ZONES, AsyncGriddy
import voluptuous as vol

from homeassistant import config_entries, core, exceptions
from homeassistant.helpers import aiohttp_client

from .const import CONF_LOADZONE
from .const import DOMAIN  # pylint:disable=unused-import

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema({vol.Required(CONF_LOADZONE): vol.In(LOAD_ZONES)})


async def validate_input(hass: core.HomeAssistant, data):
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """
    client_session = aiohttp_client.async_get_clientsession(hass)

    try:
        await AsyncGriddy(
            client_session, settlement_point=data[CONF_LOADZONE]
        ).async_getnow()
    except (asyncio.TimeoutError, ClientError):
        raise CannotConnect

    # Return info that you want to store in the config entry.
    return {"title": f"Load Zone {data[CONF_LOADZONE]}"}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Griddy Power."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        info = None
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

            if "base" not in errors:
                await self.async_set_unique_id(user_input[CONF_LOADZONE])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    async def async_step_import(self, user_input):
        """Handle import."""
        await self.async_set_unique_id(user_input[CONF_LOADZONE])
        self._abort_if_unique_id_configured()

        return await self.async_step_user(user_input)


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""
