"""Config flow for Smart Meter B Route integration."""

import logging
from typing import Any

from momonga import Momonga, MomongaSkJoinFailure, MomongaSkScanFailure
from serial.tools.list_ports import comports
from serial.tools.list_ports_common import ListPortInfo
import voluptuous as vol

from homeassistant.components.usb import get_serial_by_id, human_readable_device_name
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_DEVICE, CONF_ID, CONF_PASSWORD
from homeassistant.core import callback
from homeassistant.helpers.service_info.usb import UsbServiceInfo

from .const import DOMAIN, ENTRY_TITLE

_LOGGER = logging.getLogger(__name__)


def _validate_input(device: str, id: str, password: str) -> None:
    """Validate the user input allows us to connect."""
    with Momonga(dev=device, rbid=id, pwd=password):
        pass


def _human_readable_device_name(port: UsbServiceInfo | ListPortInfo) -> str:
    return human_readable_device_name(
        port.device,
        port.serial_number,
        port.manufacturer,
        port.description,
        str(port.vid) if port.vid else None,
        str(port.pid) if port.pid else None,
    )


class BRouteConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Smart Meter B Route."""

    VERSION = 1

    device: UsbServiceInfo | None = None

    @callback
    def _get_discovered_device_id_and_name(
        self, device_options: dict[str, ListPortInfo]
    ) -> tuple[str | None, str | None]:
        discovered_device_id = (
            get_serial_by_id(self.device.device) if self.device else None
        )
        discovered_device = (
            device_options.get(discovered_device_id) if discovered_device_id else None
        )
        discovered_device_name = (
            _human_readable_device_name(discovered_device)
            if discovered_device
            else None
        )
        return discovered_device_id, discovered_device_name

    async def _get_usb_devices(self) -> dict[str, ListPortInfo]:
        """Return a list of available USB devices."""
        devices = await self.hass.async_add_executor_job(comports)
        return {get_serial_by_id(port.device): port for port in devices}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        device_options = await self._get_usb_devices()
        if user_input is not None:
            try:
                await self.hass.async_add_executor_job(
                    _validate_input,
                    user_input[CONF_DEVICE],
                    user_input[CONF_ID],
                    user_input[CONF_PASSWORD],
                )
            except MomongaSkScanFailure:
                errors["base"] = "cannot_connect"
            except MomongaSkJoinFailure:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(
                    user_input[CONF_ID], raise_on_progress=False
                )
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=ENTRY_TITLE, data=user_input)

        discovered_device_id, discovered_device_name = (
            self._get_discovered_device_id_and_name(device_options)
        )
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_DEVICE, default=discovered_device_id): vol.In(
                        {discovered_device_id: discovered_device_name}
                        if discovered_device_id and discovered_device_name
                        else {
                            name: _human_readable_device_name(device)
                            for name, device in device_options.items()
                        }
                    ),
                    vol.Required(CONF_ID): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )
