"""Config flow for Antifurto365 iAlarmXR integration."""
import logging

from pyialarmxr import IAlarmXR
import voluptuous as vol

from homeassistant import config_entries, core
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.data_entry_flow import FlowResult

from .const import DEFAULT_HOST, DEFAULT_PORT, DOMAIN

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST, default=DEFAULT_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


async def _get_device_mac(
    hass: core.HomeAssistant, host: str, username: str, password: str, port: int
) -> str:
    ialarmxr = IAlarmXR(host, username, password, port)
    return await hass.async_add_executor_job(ialarmxr.get_mac)


class IAlarmConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Antifurto365 iAlarmXR."""

    VERSION = 1

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Handle the initial step."""
        errors = {}
        mac = None

        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=DATA_SCHEMA)

        host = user_input[CONF_HOST]
        port = user_input[CONF_PORT]
        username = user_input[CONF_USERNAME]
        password = user_input[CONF_PASSWORD]

        try:
            # If we are able to get the MAC address, we are able to establish
            # a connection to the device.
            mac = await _get_device_mac(self.hass, host, username, password, port)
        except ConnectionError:
            errors["base"] = "cannot_connect"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"

        if errors:
            return self.async_show_form(
                step_id="user", data_schema=DATA_SCHEMA, errors=errors
            )

        await self.async_set_unique_id(mac)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(title=user_input[CONF_HOST], data=user_input)
