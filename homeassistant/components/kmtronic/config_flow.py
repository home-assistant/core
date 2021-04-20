"""Config flow for kmtronic integration."""
import logging

import aiohttp
from pykmtronic.auth import Auth
from pykmtronic.hub import KMTronicHubAPI
import voluptuous as vol

from homeassistant import config_entries, core, exceptions
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.helpers import aiohttp_client

from .const import CONF_REVERSE, DOMAIN

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


async def validate_input(hass: core.HomeAssistant, data):
    """Validate the user input allows us to connect."""
    session = aiohttp_client.async_get_clientsession(hass)
    auth = Auth(
        session,
        f"http://{data[CONF_HOST]}",
        data[CONF_USERNAME],
        data[CONF_PASSWORD],
    )
    hub = KMTronicHubAPI(auth)

    try:
        await hub.async_get_status()
    except aiohttp.client_exceptions.ClientResponseError as err:
        raise InvalidAuth from err
    except aiohttp.client_exceptions.ClientConnectorError as err:
        raise CannotConnect from err

    return data


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for kmtronic."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return KMTronicOptionsFlow(config_entry)

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)

                return self.async_create_entry(title=info["host"], data=user_input)
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


class KMTronicOptionsFlow(config_entries.OptionsFlow):
    """Handle options."""

    def __init__(self, config_entry):
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_REVERSE,
                        default=self.config_entry.options.get(CONF_REVERSE),
                    ): bool,
                }
            ),
        )
