"""Config flow for Nightscout integration."""
from asyncio import TimeoutError as AsyncIOTimeoutError
import logging

from aiohttp import ClientError
from py_nightscout import Api as NightscoutAPI
import voluptuous as vol

from homeassistant import config_entries, exceptions
from homeassistant.const import CONF_URL

from .const import DOMAIN  # pylint:disable=unused-import

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema({vol.Required(CONF_URL): str})


async def _validate_input(data):
    """Validate the user input allows us to connect."""

    try:
        api = NightscoutAPI(data[CONF_URL])
        status = await api.get_server_status()
    except (ClientError, AsyncIOTimeoutError, OSError):
        raise CannotConnect

    # Return info to be stored in the config entry.
    return {"title": status.name}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Nightscout."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            try:
                info = await _validate_input(user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""
