"""Config flow for Kostal Plenticore Solar Inverter integration."""
from asyncio.exceptions import TimeoutError as AsyncIOTimeoutError
import logging

from aiohttp.client_exceptions import ClientError
from kostal.plenticore import PlenticoreApiClient, PlenticoreAuthenticationException
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_BASE, CONF_HOST, CONF_NAME, CONF_PASSWORD
from homeassistant.core import callback, HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME, default="Plenticore"): str,
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


@callback
def configured_instances(hass):
    """Return a set of configured Kostal Plenticore HOSTS."""
    return set(
        entry.data[CONF_HOST] for entry in hass.config_entries.async_entries(DOMAIN)
    )


async def test_connection(hass: HomeAssistant, data) -> str:
    """Test the connection to the inverter.

    Data has the keys from DATA_SCHEMA with values provided by the user.

    Returns the hostname and serial number
    """

    session = async_get_clientsession(hass)
    async with PlenticoreApiClient(session, data["host"]) as client:
        await client.login(data["password"])
        settings = await client.get_setting_values(
            {"scb:network": ["Hostname"], "devices:local": ["Properties:SerialNo"]}
        )
        device_hostname = settings["scb:network"]["Hostname"]
        serial_no = settings["devices:local"]["Properties:SerialNo"]

        return device_hostname, serial_no


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Kostal Plenticore Solar Inverter."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self):
        """Initialize a new ConfigFlow instance."""
        self._errors = {}

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        self._errors = {}

        if user_input is not None:
            if user_input[CONF_HOST] not in configured_instances(self.hass):
                try:
                    await test_connection(self.hass, user_input)

                    return self.async_create_entry(
                        title=user_input[CONF_NAME], data=user_input
                    )
                except PlenticoreAuthenticationException as ex:
                    self._errors[CONF_PASSWORD] = "invalid_auth"
                    _LOGGER.exception("Error response: %s", ex.msg)
                except ClientError:
                    self._errors[CONF_HOST] = "cannot_connect"
                except AsyncIOTimeoutError:
                    self._errors[CONF_HOST] = "cannot_connect"
                except Exception:  # pylint: disable=broad-except
                    _LOGGER.exception("Unexpected exception")
                    self._errors[CONF_BASE] = "unknown"
            else:
                return self.async_abort(reason="already_configured")

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=self._errors
        )
