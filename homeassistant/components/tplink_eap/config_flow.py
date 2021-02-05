"""Config flow for TP-Link EAP integration."""
import logging
from typing import Any, Dict

from pytleap.eap import Eap
from pytleap.error import AuthenticationError, CommunicationError
import voluptuous as vol

from homeassistant import config_entries, core, exceptions
from homeassistant.const import CONF_PASSWORD, CONF_URL, CONF_USERNAME

# pylint: disable=unused-import
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_URL): str,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


async def validate_input(hass: core.HomeAssistant, data):
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """
    # Validate the data can be used to set up a connection.
    eap = Eap(data[CONF_URL], data[CONF_USERNAME], data[CONF_PASSWORD])

    try:
        await eap.connect()
    except AuthenticationError as ex:
        raise InvalidAuth from ex
    except CommunicationError as ex:
        raise CannotConnect from ex
    finally:
        await eap.disconnect()

    # Return info that you want to store in the config entry.
    return {"title": f"TP-Link EAP {eap.name}", "data": data}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for TP-Link EAP."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            if self._already_configured(user_input):
                return self.async_abort(reason="already_configured")

            try:
                info = await validate_input(self.hass, user_input)
                return self.async_create_entry(**info)
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

    def _already_configured(self, user_input: Dict[str, Any]) -> bool:
        """See if we already have a device matching user input configured."""
        return user_input[CONF_URL] in [
            entry.data[CONF_URL] for entry in self._async_current_entries()
        ]


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""
