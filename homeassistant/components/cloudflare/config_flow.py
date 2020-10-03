"""Config flow for Cloudflare integration."""
import logging

from pycfdns import CloudflareUpdater
import voluptuous as vol

from homeassistant.config_entries import (
    CONN_CLASS_CLOUD_PUSH,
    SOURCE_USER,
    ConfigFlow,
)
from homeassistant.const import CONF_API_KEY, CONF_EMAIL, CONF_ZONE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN  # pylint:disable=unused-import

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): str, 
        vol.Required(CONF_API_KEY): str,
        vol.Required(CONF_ZONE): str
    }
)


async def validate_input(hass: HomeAssistant, data):
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """
    cfupdate = CloudflareUpdater(
        async_get_clientsession(),
        data[CONF_EMAIL],
        data[CONF_TOKEN],
        data[CONF_ZONE],
        {},
    )

    try:
        await cfupdate.get_zone_id()
    except CloudflareException as error:
        raise CannotConnect from error

    # Return info that you want to store in the config entry.
    return {"title": data[CONF_ZONE]}


class CloudflareConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Cloudflare."""

    VERSION = 1
    CONNECTION_CLASS = CONN_CLASS_CLOUD_PUSH

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
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


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""
