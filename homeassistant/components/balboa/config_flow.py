"""Config flow for Balboa Spa integration."""
import logging

from pybalboa import BalboaSpaWifi
import voluptuous as vol

from homeassistant import config_entries, core, exceptions
from homeassistant.const import CONF_HOST, CONF_NAME

from .const import DOMAIN  # pylint:disable=unused-import

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {vol.Required(CONF_HOST): str, vol.Required(CONF_NAME, default="Spa"): str}
)


async def validate_input(hass: core.HomeAssistant, data):
    """Validate the user input allows us to connect."""
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.data[CONF_HOST] == data[CONF_HOST]:
            raise AlreadyConfigured

    _LOGGER.debug("Attempting to connect to %s", data[CONF_HOST])
    spa = BalboaSpaWifi(data[CONF_HOST])
    connected = await spa.connect()
    _LOGGER.debug("Got connected = %d", connected)
    if not connected:
        raise CannotConnect
    await spa.disconnect()

    return {"title": "Balboa Spa"}


class DomainConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Balboa Spa."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)

                return self.async_create_entry(title=info["title"], data=user_input)
            except AlreadyConfigured:
                return self.async_abort(reason="already_configured")
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class AlreadyConfigured(exceptions.HomeAssistantError):
    """Error to indicate this device is already configured."""
