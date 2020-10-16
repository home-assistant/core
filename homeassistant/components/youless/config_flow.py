"""Config flow for youless integration."""
import logging
from urllib.error import HTTPError, URLError

import voluptuous as vol
from youless_api.youless_api import YoulessAPI

from homeassistant import config_entries, core, exceptions
from homeassistant.const import CONF_DEVICE, CONF_HOST, CONF_NAME

from .const import DOMAIN  # pylint:disable=unused-import

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema({vol.Required(CONF_NAME): str, vol.Required(CONF_HOST): str})


async def validate_input(hass: core.HomeAssistant, data):
    """Validate the user input using the API connector."""
    try:
        api = YoulessAPI(data[CONF_HOST])
        await hass.async_add_executor_job(api.initialize)
    except HTTPError as exception:
        raise CannotConnect() from exception
    except URLError as exception:
        raise CannotConnect() from exception

    return {"title": data[CONF_NAME]}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for youless."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)

                return self.async_create_entry(
                    title=info["title"],
                    data={
                        CONF_HOST: user_input[CONF_HOST],
                        CONF_NAME: user_input[CONF_NAME],
                        CONF_DEVICE: user_input[CONF_NAME],
                    },
                )
            except CannotConnect:
                _LOGGER.exception("Cannot connect to host")
                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""
