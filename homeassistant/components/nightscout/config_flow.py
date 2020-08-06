"""Config flow for NightScout integration."""
from asyncio import TimeoutError as AsyncIOTimeoutError
from datetime import timedelta
import logging

from aiohttp import ClientError
from py_nightscout import Api as NightScoutAPI
import voluptuous as vol

from homeassistant import config_entries, exceptions
from homeassistant.const import CONF_HOST

from .const import DOMAIN  # pylint:disable=unused-import

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema({vol.Required(CONF_HOST): str})


async def _validate_input(data):
    """Validate the user input allows us to connect."""

    try:
        api = NightScoutAPI(data[CONF_HOST])
        status = await api.get_server_status()
    except (ClientError, AsyncIOTimeoutError, OSError):
        raise CannotConnect

    # Return info to be stored in the config entry.
    return {"title": status.name}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for NightScout."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL
    SCAN_INTERVAL = timedelta(minutes=5)

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
