"""Config flow for flo integration."""
from aioflo import async_get_api
from aioflo.errors import RequestError
import voluptuous as vol

from homeassistant import config_entries, core, exceptions
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, LOGGER  # pylint:disable=unused-import

DATA_SCHEMA = vol.Schema({"username": str, "password": str})


async def validate_input(hass: core.HomeAssistant, data):
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """

    session = async_get_clientsession(hass)
    try:
        api = await async_get_api(
            data[CONF_USERNAME], data[CONF_PASSWORD], session=session
        )
    except RequestError as request_error:
        LOGGER.error("Error connecting to the Flo API: %s", request_error)
        raise CannotConnect from request_error

    user_info = await api.user.get_info()
    a_location_id = user_info["locations"][0]["id"]
    location_info = await api.location.get_info(a_location_id)
    return {"title": location_info["nickname"]}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for flo."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_USERNAME])
            self._abort_if_unique_id_configured()
            try:
                info = await validate_input(self.hass, user_input)
                return self.async_create_entry(title=info["title"], data=user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""
