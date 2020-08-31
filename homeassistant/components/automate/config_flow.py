"""Config flow for Automate Pulse Hub v2 integration."""
import logging

import aiopulse2
import voluptuous as vol

from homeassistant import config_entries, core, exceptions

from .const import DOMAIN  # pylint:disable=unused-import

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema({vol.Required("host"): str})


async def validate_input(hass: core.HomeAssistant, data):
    """Validate the user input allows us to connect to the hub.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """
    hub = aiopulse2.Hub(data["host"])
    try:
        await hub.test()
    except Exception as err:
        raise CannotConnect(str(err))  # pylint: disable=raise-missing-from

    # Return info that you want to store in the config entry.
    return {"title": hub.name}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Automate Pulse Hub v2."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    async def async_step_user(self, user_input=None):
        """Handle the initial step once we have info from the user."""
        errors = {}
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)

                return self.async_create_entry(title=info["title"], data=user_input)
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
