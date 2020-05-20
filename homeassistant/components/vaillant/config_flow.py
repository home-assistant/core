"""Config flow for vaillant integration."""
import logging

from pymultimatic.api import ApiError
import voluptuous as vol

from homeassistant import config_entries, core, exceptions
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from . import ApiHub
from .const import CONF_SERIAL_NUMBER, DOMAIN  # pylint:disable=unused-import

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Optional(CONF_SERIAL_NUMBER): str,
    }
)


async def validate_input(hass: core.HomeAssistant, data):
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """

    await validate_authentication(
        hass, data[CONF_USERNAME], data[CONF_PASSWORD], data.get(CONF_SERIAL_NUMBER)
    )

    return {"title": "Vaillant"}


async def validate_authentication(hass, username, password, serial):
    """Ensure provided credentials are working."""
    hub: ApiHub = ApiHub(hass, username, password, serial)
    try:
        if not await hub.authenticate():
            raise InvalidAuth
    except ApiError as err:
        resp = await err.response.json()
        _LOGGER.exception(
            "Unable to authenticate, API says: %s, status: %s",
            resp,
            err.response.status,
        )
        raise InvalidAuth from err


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for vaillant."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
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
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""
