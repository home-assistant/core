"""Config Flow for ComfoAir."""
import os
from typing import Any, Dict, Optional

import serial.tools.list_ports
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME

from .const import (  # pylint:disable=unused-import
    CONF_SERIAL_PORT,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DOMAIN,
)

CONF_MANUAL_PATH = "Enter Manually"


class ComfoAirConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """ComfoAir config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    async def async_step_user(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Handle a flow initialized by the user."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        ports = await self.hass.async_add_executor_job(serial.tools.list_ports.comports)
        list_of_ports = [
            f"{p}, s/n: {p.serial_number or 'n/a'}"
            + (f" - {p.manufacturer}" if p.manufacturer else "")
            for p in ports
        ]
        list_of_ports.append(CONF_MANUAL_PATH)

        if user_input is not None:
            user_selection = user_input[CONF_SERIAL_PORT]
            if user_selection == CONF_MANUAL_PATH:
                return await self.async_step_port_config()

            port = ports[list_of_ports.index(user_selection)]
            user_input[CONF_SERIAL_PORT] = await self.hass.async_add_executor_job(
                get_serial_by_id, port.device
            )

            title = f"{port.description}, s/n: {port.serial_number or 'n/a'}"
            title += f" - {port.manufacturer}" if port.manufacturer else ""

            return self.async_create_entry(title=title, data=user_input)

        schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default=DEFAULT_NAME): str,
                vol.Required(CONF_SERIAL_PORT, default=list_of_ports[0]): vol.In(
                    list_of_ports
                ),
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema)

    async def async_step_port_config(self, user_input=None):
        """Enter port settings specific for this type of radio."""
        if user_input is not None:
            user_input[CONF_SERIAL_PORT] = await self.hass.async_add_executor_job(
                get_serial_by_id, user_input[CONF_SERIAL_PORT]
            )
            return self.async_create_entry(
                title=user_input[CONF_SERIAL_PORT], data=user_input,
            )

        schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default=DEFAULT_NAME): str,
                vol.Required(CONF_SERIAL_PORT, default=DEFAULT_PORT): str,
            }
        )
        return self.async_show_form(step_id="port_config", data_schema=schema)

    async def async_step_import(self, user_input=None):
        """Import a config entry."""
        return await self.async_step_port_config(user_input)


def get_serial_by_id(dev_path: str) -> str:
    """Return a /dev/serial/by-id match for given device if available."""
    by_id = "/dev/serial/by-id"
    if not os.path.isdir(by_id):
        return dev_path

    for path in (entry.path for entry in os.scandir(by_id) if entry.is_symlink()):
        if os.path.realpath(path) == dev_path:
            return path

    return dev_path
