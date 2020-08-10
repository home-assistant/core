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


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Nightscout."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    async def _validate_input(self, data):
        """Validate the user input allows us to connect."""
        url = data[CONF_URL]
        try:
            api = NightscoutAPI(url)
            status = await api.get_server_status()
        except (ClientError, AsyncIOTimeoutError, OSError):
            raise InputValidationError("cannot_connect")

        # Return info to be stored in the config entry.
        return {"title": status.name}

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            try:
                return await self._try_create_entry(user_input)
            except InputValidationError as error:
                errors["base"] = error.base

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    async def _try_create_entry(self, data):
        unique_id = hash_from_url(data[CONF_URL])
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured()
        info = await self._validate_input(data)
        return self.async_create_entry(title=info["title"], data=data)


class InputValidationError(exceptions.HomeAssistantError):
    """Error to indicate we cannot proceed due to invalid input."""

    def __init__(self, base: str):
        """Initialize with error base."""
        super().__init__()
        self.base = base
