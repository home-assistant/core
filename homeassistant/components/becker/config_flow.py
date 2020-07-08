"""Config flow to configure Becker component."""
import logging
import os

import serial.tools.list_ports
import voluptuous as vol

from homeassistant import config_entries

from .const import CONF_DEVICE, CONF_DEVICE_PATH, DOMAIN  # pylint:disable=unused-import

_LOGGER = logging.getLogger(__name__)
CONF_MANUAL_PATH = "Enter Manually"


class BeckerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Becker config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    def __init__(self):
        """Initialize the Becker config flow."""
        self.device = CONF_DEVICE

    async def async_step_user(self, user_input=None):
        """Handle a flow start."""
        if self._async_current_entries():
            return self.async_abort(reason="one_instance_only")

        ports = await self.hass.async_add_executor_job(serial.tools.list_ports.comports)
        list_of_ports = [
            f"{p}, s/n: {p.serial_number or 'n/a'}"
            + (f" - {p.manufacturer}" if p.manufacturer else "")
            for p in ports
        ]

        if user_input is not None:
            user_selection = user_input[CONF_DEVICE_PATH]

            port = ports[list_of_ports.index(user_selection)]
            dev_path = await self.hass.async_add_executor_job(
                get_serial_by_id, port.device
            )

            self._device_path = dev_path
            return await self.async_step_port_config()

        schema = vol.Schema({vol.Required(CONF_DEVICE_PATH): vol.In(list_of_ports)})
        return self.async_show_form(step_id="user", data_schema=schema)

    async def async_step_import(self, info):
        """Import existing configuration from Becker Cover."""
        if self._async_current_entries():
            return self.async_abort(reason="already_configured")

        return self.async_create_entry(
            title="Becker Cover (import from configuration.yaml)",
            data={CONF_DEVICE_PATH: info.get(CONF_DEVICE_PATH)},
        )

    async def async_step_port_config(self, user_input=None):
        """Enter port settings specific for this type of radio."""
        errors = {}

        if user_input is not None:
            self._device_path = user_input.get(CONF_DEVICE_PATH)
            serial_by_id = await self.hass.async_add_executor_job(
                get_serial_by_id, user_input[CONF_DEVICE_PATH]
            )
            user_input[CONF_DEVICE_PATH] = serial_by_id
            return self.async_create_entry(
                title=user_input[CONF_DEVICE_PATH], data=user_input,
            )

        schema = {
            vol.Required(
                CONF_DEVICE_PATH, default=self._device_path or vol.UNDEFINED
            ): str
        }

        return self.async_show_form(
            step_id="port_config", data_schema=vol.Schema(schema), errors=errors,
        )


def get_serial_by_id(dev_path: str) -> str:
    """Return a /dev/serial/by-id match for given device if available."""
    by_id = "/dev/serial/by-id"
    if not os.path.isdir(by_id):
        return dev_path

    for path in (entry.path for entry in os.scandir(by_id) if entry.is_symlink()):
        if os.path.realpath(path) == dev_path:
            return path
    return dev_path
