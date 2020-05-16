"""Config flow for the Plugwise_stick platform."""
import logging
import os

import plugwise
from plugwise.exceptions import (
    CirclePlusError,
    NetworkDown,
    PortError,
    StickInitError,
    TimeoutException,
)
import serial.tools.list_ports
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.util import slugify

from .const import CONF_USB_PATH, DOMAIN

_LOGGER = logging.getLogger(__name__)
CONF_MANUAL_PATH = "Enter Manually"
CONF_DEFAULT_NAME = "Plugwise USB-stick"


@callback
def plugwise_stick_entries(hass: HomeAssistant):
    """Return existing connections for Plugwise USB-stick domain."""
    return {
        (entry.data[CONF_USB_PATH])
        for entry in hass.config_entries.async_entries(DOMAIN)
    }


class PlugwiseConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    def __init__(self):
        """Initialize the Plugwise USB-stick config flow."""
        self._name = None
        self._list_of_ports = []

    async def async_step_user(self, user_input=None):
        """Step when user initializes a integration."""
        errors = {}
        ports = await self.hass.async_add_executor_job(serial.tools.list_ports.comports)
        self._list_of_ports = [
            f"{p}, s/n: {p.serial_number or 'n/a'}"
            + (f" - {p.manufacturer}" if p.manufacturer else "")
            for p in ports
        ]
        self._list_of_ports.append(CONF_MANUAL_PATH)

        if user_input is not None:
            user_selection = user_input[CONF_USB_PATH]
            if user_selection == CONF_MANUAL_PATH:
                return await self.async_step_manual_path()
            else:
                port = ports[self._list_of_ports.index(user_selection)]
                device_path = await self.hass.async_add_executor_job(
                    get_serial_by_id, port.device
                )
            errors = await self.async_validate_connection(device_path)
            if not errors:
                return self.async_create_entry(
                    title=device_path, data={CONF_USB_PATH: device_path}
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USB_PATH): vol.In(self._list_of_ports),
                }
            ),
            errors=errors,
        )

    async def async_step_manual_path(self, user_input=None):
        """Step when manual path to device"""
        errors = None

        if user_input is not None:
            device_path = await self.hass.async_add_executor_job(
                get_serial_by_id, user_input.get(CONF_USB_PATH)
            )
            errors = await self.async_validate_connection(device_path)

            if not errors:
                return self.async_create_entry(
                    title=device_path, data={CONF_USB_PATH: device_path}
                )
        return self.async_show_form(
            step_id="manual_path",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_USB_PATH, default="/dev/ttyUSB0" or vol.UNDEFINED
                    ): str
                }
            ),
            errors=errors if errors else {},
        )

    async def async_validate_connection(self, device_path=None):
        """Test if device_path is a real Plugwise USB-Stick."""
        errors = {}
        if device_path is None:
            errors["base"] = "connection_failed"
            return errors
        if device_path in plugwise_stick_entries(self.hass):
            errors["base"] = "connection_exists"
            return errors
        stick = await self.hass.async_add_executor_job(plugwise.stick, device_path)
        try:
            await self.hass.async_add_executor_job(stick.connect)
            await self.hass.async_add_executor_job(stick.initialize_stick)
            await self.hass.async_add_executor_job(stick.disconnect)
        except PortError:
            errors["base"] = "cannot_connect"
        except StickInitError:
            errors["base"] = "stick_init"
        except NetworkDown:
            errors["base"] = "network_down"
        except TimeoutException:
            errors["base"] = "network_timeout"
        return errors


def get_serial_by_id(dev_path: str) -> str:
    """Return a /dev/serial/by-id match for given device if available."""
    by_id = "/dev/serial/by-id"
    if not os.path.isdir(by_id):
        return dev_path
    for path in (entry.path for entry in os.scandir(by_id) if entry.is_symlink()):
        if os.path.realpath(path) == dev_path:
            return path
    return dev_path
