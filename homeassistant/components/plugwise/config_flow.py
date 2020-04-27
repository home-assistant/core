"""Config flow for Plugwise integration."""
import logging
from typing import Any, Dict

from Plugwise_Smile.Smile import Smile
import voluptuous as vol

from homeassistant import config_entries, core, exceptions
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN  # pylint:disable=unused-import

_LOGGER = logging.getLogger(__name__)


def _get_config_schema(input_dict: Dict[str, Any] = None) -> vol.Schema:
    """
    Return schema defaults for init step based on user input/config dict.

    Retain info already provided for future form views by setting them as defaults in schema.
    """
    if input_dict is None:
        input_dict = {}

    return vol.Schema({vol.Required("host"): str, vol.Required("password"): str})


async def validate_input(hass: core.HomeAssistant, data):
    """
    Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """
    websession = async_get_clientsession(hass, verify_ssl=False)
    api = Smile(
        host=data["host"], password=data["password"], timeout=30, websession=websession
    )

    if not await api.connect():
        raise CannotConnect

    return {"title": api.smile_name}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Plugwise Smile."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self) -> None:
        """Initialize config flow."""
        self._user_schema = None

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        self._user_schema = _get_config_schema(user_input)
        if user_input is not None:

            try:
                info = await validate_input(self.hass, user_input)

                return self.async_create_entry(title=info["title"], data=user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user", data_schema=self._user_schema, errors=errors
        )


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""
