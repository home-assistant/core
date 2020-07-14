"""Adds config flow for Growatt RS232."""

import logging

from growattRS232 import (
    ATTR_SERIAL_NUMBER,
    GrowattRS232,
    ModbusException,
    PortException,
)
from growattRS232.const import DEFAULT_ADDRESS, DEFAULT_PORT
import voluptuous as vol

from homeassistant import config_entries, exceptions
from homeassistant.const import CONF_ADDRESS, CONF_PORT

from .const import DOMAIN  # pylint:disable=unused-import

_LOGGER = logging.getLogger(__name__)

CONF_MANUAL_PATH = "Enter Manually"

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PORT, default=DEFAULT_PORT): str,
        vol.Required(CONF_ADDRESS, default=DEFAULT_ADDRESS): int,
    }
)


class GrowattRS232FlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for GrowattRS232 inverter."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self):
        """Initialize."""

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        errors = {}

        if user_input is not None:
            try:
                data = {}
                growattrs232 = GrowattRS232(
                    user_input[CONF_PORT], user_input[CONF_ADDRESS]
                )
                data = await growattrs232.async_update()
                serial_number = data.get(ATTR_SERIAL_NUMBER, "").lower()
                if serial_number == "":
                    raise MissingSerialNumber
                await self.async_set_unique_id(serial_number)
                self._abort_if_unique_id_configured()
                title = f"Growatt {serial_number}"
                return self.async_create_entry(title=title, data=user_input)
            except PortException:
                errors[CONF_PORT] = "port_error"
            except ModbusException:
                errors[CONF_ADDRESS] = "modbus_error"
            except ConnectionError:
                errors["base"] = "connection_error"
            except MissingSerialNumber:
                return self.async_abort(reason="serial_number_error")

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )


class MissingSerialNumber(exceptions.HomeAssistantError):
    """Error to indicate that the serial number is missing."""
