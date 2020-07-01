"""Config flow for Plugwise integration."""
import logging

from Plugwise_Smile.Smile import Smile
import voluptuous as vol

from homeassistant import config_entries, core, exceptions
from homeassistant.const import CONF_HOST, CONF_PASSWORD
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN  # pylint:disable=unused-import

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {vol.Required(CONF_HOST): str, vol.Required(CONF_PASSWORD): str}
)


async def validate_input(hass: core.HomeAssistant, data):
    """
    Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """
    websession = async_get_clientsession(hass, verify_ssl=False)
    api = Smile(
        host=data["host"], password=data["password"], timeout=30, websession=websession
    )

    try:
        await api.connect()
    except Smile.InvalidAuthentication:
        raise InvalidAuth
    except Smile.ConnectionFailedError:
        raise CannotConnect

    return api


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Plugwise Smile."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:

            try:
                api = await validate_input(self.hass, user_input)

                return self.async_create_entry(title=api.smile_name, data=user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

            if not errors:
                await self.async_set_unique_id(api.gateway_id)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(title=api.smile_name, data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""
