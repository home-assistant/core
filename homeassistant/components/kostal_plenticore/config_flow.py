"""Config flow for Kostal Plenticore Solar Inverter integration."""

import logging

from aiohttp.client_exceptions import ClientError
from pykoplenti import ApiClient, AuthenticationException
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_BASE, CONF_HOST, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN
from .helper import get_hostname_id

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


async def test_connection(hass: HomeAssistant, data) -> str:
    """Test the connection to the inverter.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """

    session = async_get_clientsession(hass)
    async with ApiClient(session, data["host"]) as client:
        await client.login(data["password"])
        hostname_id = await get_hostname_id(client)
        values = await client.get_setting_values("scb:network", hostname_id)

    return values["scb:network"][hostname_id]


class KostalPlenticoreConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Kostal Plenticore Solar Inverter."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        hostname = None

        if user_input is not None:
            self._async_abort_entries_match({CONF_HOST: user_input[CONF_HOST]})

            try:
                hostname = await test_connection(self.hass, user_input)
            except AuthenticationException as ex:
                errors[CONF_PASSWORD] = "invalid_auth"
                _LOGGER.error("Error response: %s", ex)
            except (ClientError, TimeoutError):
                errors[CONF_HOST] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors[CONF_BASE] = "unknown"

            if not errors:
                return self.async_create_entry(title=hostname, data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )
