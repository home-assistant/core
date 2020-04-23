"""Config flow for SMS integration."""
import logging

import gammu  # pylint: disable=import-error, no-member
import voluptuous as vol

from homeassistant import config_entries, core, exceptions
from homeassistant.const import CONF_DEVICE

from .const import DOMAIN  # pylint:disable=unused-import

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema({vol.Required(CONF_DEVICE): str})


async def validate_input(hass: core.HomeAssistant, data):
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """
    device = data[CONF_DEVICE]
    gateway = gammu.StateMachine()  # pylint: disable=no-member
    try:
        gateway.SetConfig(0, dict(Device=device, Connection="at"))
        gateway.Init()
    except gammu.GSMError:  # pylint: disable=no-member
        raise CannotConnect
    finally:
        gateway.Terminate()

    # Return info that you want to store in the config entry.
    return {"title": device}


class SMSFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for SMS integration."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

            if "base" not in errors:
                await self.async_set_unique_id(user_input[CONF_DEVICE])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    async def async_step_import(self, user_input):
        """Handle import."""
        await self.async_set_unique_id(user_input[CONF_DEVICE])
        self._abort_if_unique_id_configured()

        return await self.async_step_user(user_input)


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""
