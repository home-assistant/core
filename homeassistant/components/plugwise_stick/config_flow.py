"""Config flow for the Plugwise_stick platform."""
import os
from typing import Dict

import plugwise
from plugwise.exceptions import NetworkDown, PortError, StickInitError, TimeoutException
import serial.tools.list_ports
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback

from .const import CONF_USB_PATH, DOMAIN

CONF_MANUAL_PATH = "Enter Manually"


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

    async def async_step_user(self, user_input=None):
        """Step when user initializes a integration."""
        errors = {}
        ports = await self.hass.async_add_executor_job(serial.tools.list_ports.comports)
        list_of_ports = [
            f"{p}, s/n: {p.serial_number or 'n/a'}"
            + (f" - {p.manufacturer}" if p.manufacturer else "")
            for p in ports
        ]
        list_of_ports.append(CONF_MANUAL_PATH)

        if user_input is not None:
            user_selection = user_input[CONF_USB_PATH]
            if user_selection == CONF_MANUAL_PATH:
                return await self.async_step_manual_path()
            if user_selection in list_of_ports:
                port = ports[list_of_ports.index(user_selection)]
                device_path = await self.hass.async_add_executor_job(
                    get_serial_by_id, port.device
                )
            else:
                device_path = await self.hass.async_add_executor_job(
                    get_serial_by_id, user_selection
                )
            errors = await validate_connection(self.hass, device_path)
            if not errors:
                return self.async_create_entry(
                    title=device_path, data={CONF_USB_PATH: device_path}
                )
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required(CONF_USB_PATH): vol.In(list_of_ports)}
            ),
            errors=errors,
        )

    async def async_step_manual_path(self, user_input=None):
        """Step when manual path to device."""
        errors = {}

        if user_input is not None:
            device_path = await self.hass.async_add_executor_job(
                get_serial_by_id, user_input.get(CONF_USB_PATH)
            )
            errors = await validate_connection(self.hass, device_path)
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


async def validate_connection(self, device_path=None) -> Dict[str, str]:
    """Test if device_path is a real Plugwise USB-Stick."""
    errors = {}
    if device_path is None:
        errors["base"] = "connection_failed"
        return errors

    if device_path in plugwise_stick_entries(self):
        errors["base"] = "connection_exists"
        return errors

    stick = await self.async_add_executor_job(plugwise.stick, device_path)
    try:
        await self.async_add_executor_job(stick.connect)
        await self.async_add_executor_job(stick.initialize_stick)
        await self.async_add_executor_job(stick.disconnect)
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
