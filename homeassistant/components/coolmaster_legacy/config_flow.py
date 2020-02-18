"""Config flow for coolmaster_legacy."""


from pycoolmaster import CoolMaster
import voluptuous as vol

from homeassistant import config_entries, core

# pylint: disable=unused-import
from .const import CONF_BAUDRATE, CONF_SERIAL_PORT, DEFAULT_BAUDRATE, DOMAIN

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_SERIAL_PORT): str,
        vol.Required(CONF_BAUDRATE, default=DEFAULT_BAUDRATE): str,
    }
)


async def _validate_connection(
    hass: core.HomeAssistant, port: str, baud: str = DEFAULT_BAUDRATE
) -> bool:
    cool = CoolMaster(port, baud)
    devices = await hass.async_add_executor_job(cool.devices)
    return bool(devices)


class CoolmasterSerialConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Coolmaster config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def _async_get_entry(self, data):
        return self.async_create_entry(
            title=data[CONF_SERIAL_PORT],
            data={
                CONF_SERIAL_PORT: data[CONF_SERIAL_PORT],
                CONF_BAUDRATE: data[CONF_BAUDRATE],
            },
        )

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=DATA_SCHEMA)

        errors = {}

        port = user_input[CONF_SERIAL_PORT]
        baud = user_input[CONF_BAUDRATE]

        try:
            result = await _validate_connection(self.hass, port, baud)
            if not result:
                errors["base"] = "no_units"
        except (ConnectionRefusedError, TimeoutError):
            errors["base"] = "connection_error"

        if errors:
            return self.async_show_form(
                step_id="user", data_schema=DATA_SCHEMA, errors=errors
            )

        return self._async_get_entry(user_input)
