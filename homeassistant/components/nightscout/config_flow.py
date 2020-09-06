"""Config flow for Nightscout integration."""
from asyncio import TimeoutError as AsyncIOTimeoutError
import logging

from aiohttp import ClientError
from py_nightscout import Api as NightscoutAPI
import voluptuous as vol

from homeassistant import config_entries, exceptions
from homeassistant.const import CONF_URL

from .const import DOMAIN  # pylint:disable=unused-import
from .utils import hash_from_url

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema({vol.Required(CONF_URL): str})


async def _validate_input(data):
    """Validate the user input allows us to connect."""
    url = data[CONF_URL]
    try:
        api = NightscoutAPI(url)
        status = await api.get_server_status()
    except (ClientError, AsyncIOTimeoutError, OSError) as error:
        raise InputValidationError("cannot_connect") from error

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
            unique_id = hash_from_url(user_input[CONF_URL])
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()
            try:
                info = await _validate_input(user_input)
            except InputValidationError as error:
                errors["base"] = error.base
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )


class InputValidationError(exceptions.HomeAssistantError):
    """Error to indicate we cannot proceed due to invalid input."""

    def __init__(self, base: str):
        """Initialize with error base."""
        super().__init__()
        self.base = base
