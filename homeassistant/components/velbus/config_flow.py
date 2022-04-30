"""Config flow for the Velbus platform."""
from __future__ import annotations

from typing import Any

import velbusaio
from velbusaio.exceptions import VelbusConnectionFailed
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import usb
from homeassistant.const import CONF_NAME, CONF_PORT
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.util import slugify

from .const import DOMAIN


@callback
def velbus_entries(hass: HomeAssistant) -> set[str]:
    """Return connections for Velbus domain."""
    return {
        entry.data[CONF_PORT] for entry in hass.config_entries.async_entries(DOMAIN)
    }


class VelbusConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the velbus config flow."""
        self._errors: dict[str, str] = {}
        self._device: str = ""
        self._title: str = ""

    def _create_device(self, name: str, prt: str) -> FlowResult:
        """Create an entry async."""
        return self.async_create_entry(title=name, data={CONF_PORT: prt})

    async def _test_connection(self, prt: str) -> bool:
        """Try to connect to the velbus with the port specified."""
        try:
            controller = velbusaio.controller.Velbus(prt)
            await controller.connect(True)
            await controller.stop()
        except VelbusConnectionFailed:
            self._errors[CONF_PORT] = "cannot_connect"
            return False
        return True

    def _prt_in_configuration_exists(self, prt: str) -> bool:
        """Return True if port exists in configuration."""
        return prt in velbus_entries(self.hass)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step when user initializes a integration."""
        self._errors = {}
        if user_input is not None:
            name = slugify(user_input[CONF_NAME])
            prt = user_input[CONF_PORT]
            if not self._prt_in_configuration_exists(prt):
                if await self._test_connection(prt):
                    return self._create_device(name, prt)
            else:
                self._errors[CONF_PORT] = "already_configured"
        else:
            user_input = {}
            user_input[CONF_NAME] = ""
            user_input[CONF_PORT] = ""

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_NAME, default=user_input[CONF_NAME]): str,
                    vol.Required(CONF_PORT, default=user_input[CONF_PORT]): str,
                }
            ),
            errors=self._errors,
        )

    async def async_step_usb(self, discovery_info: usb.UsbServiceInfo) -> FlowResult:
        """Handle USB Discovery."""
        await self.async_set_unique_id(
            f"{discovery_info.vid}:{discovery_info.pid}_{discovery_info.serial_number}_{discovery_info.manufacturer}_{discovery_info.description}"
        )
        dev_path = await self.hass.async_add_executor_job(
            usb.get_serial_by_id, discovery_info.device
        )
        # check if this device is not already configured
        if self._prt_in_configuration_exists(dev_path):
            return self.async_abort(reason="already_configured")
        # check if we can make a valid velbus connection
        if not await self._test_connection(dev_path):
            return self.async_abort(reason="cannot_connect")
        # store the data for the config step
        self._device = dev_path
        self._title = "Velbus USB"
        # call the config step
        self._set_confirm_only()
        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle Discovery confirmation."""
        if user_input is not None:
            return self._create_device(self._title, self._device)

        return self.async_show_form(
            step_id="discovery_confirm",
            description_placeholders={CONF_NAME: self._title},
        )
