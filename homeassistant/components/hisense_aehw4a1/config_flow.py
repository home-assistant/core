"""Config flow for Hisense AEH-W4A1 integration."""
import logging

<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
from pyaehw4a1.aehw4a1 import AehW4a1

from homeassistant import config_entries
from homeassistant.helpers import config_entry_flow


from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def _async_has_devices(hass):
    """Return if there are devices that can be discovered."""
    aehw4a1_ip_addresses = AehW4a1().discovery()
    return len(aehw4a1_ip_addresses) > 0


config_entry_flow.register_discovery_flow(
    DOMAIN, "Hisense AEH-W4A1", _async_has_devices, config_entries.CONN_CLASS_LOCAL_POLL
)
=======
import voluptuous as vol
=======
from homeassistant.helpers import config_entry_flow
from homeassistant import config_entries
>>>>>>> First working release, but there's a lot to do
=======
from pyaehw4a1.aehw4a1 import AehW4a1

from homeassistant import config_entries
from homeassistant.helpers import config_entry_flow
>>>>>>> Latest updates for TOX


from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def _async_has_devices(hass):
    """Return if there are devices that can be discovered."""
    aehw4a1_ip_addresses = AehW4a1().discovery()
    return len(aehw4a1_ip_addresses) > 0


<<<<<<< HEAD
    Data has the keys from DATA_SCHEMA with values provided by the user.
    """
    # TODO validate the data can be used to set up a connection.
    # If you cannot connect:
    # throw CannotConnect
    # If the authentication is wrong:
    # InvalidAuth

    # Return some info we want to store in the config entry.
    return {"title": "Name of the device"}


class DomainConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Hisense AEH-W4A1."""

    VERSION = 1
    # TODO pick one of the available connection classes in homeassistant/config_entries.py
    CONNECTION_CLASS = config_entries.CONN_CLASS_UNKNOWN

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
>>>>>>> First commit
=======
config_entry_flow.register_discovery_flow(
    DOMAIN, "Hisense AEH-W4A1", _async_has_devices, config_entries.CONN_CLASS_LOCAL_POLL
)
>>>>>>> First working release, but there's a lot to do
