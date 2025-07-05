"""Config flow for the Velbus platform."""

from __future__ import annotations

from typing import Any

import serial.tools.list_ports
import velbusaio.controller
from velbusaio.exceptions import VelbusConnectionFailed
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PASSWORD, CONF_PORT
from homeassistant.helpers.service_info.usb import UsbServiceInfo

from .const import CONF_TLS, DOMAIN


class VelbusConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 2
    MINOR_VERSION = 2

    def __init__(self) -> None:
        """Initialize the velbus config flow."""
        self._errors: dict[str, str] = {}
        self._device: str = ""
        self._title: str = ""

    def _create_device(self) -> ConfigFlowResult:
        """Create an entry async."""
        return self.async_create_entry(
            title=self._title, data={CONF_PORT: self._device}
        )

    async def _test_connection(self) -> bool:
        """Try to connect to the velbus with the port specified."""
        try:
            controller = velbusaio.controller.Velbus(self._device)
            await controller.connect()
            await controller.stop()
        except VelbusConnectionFailed:
            self._errors[CONF_PORT] = "cannot_connect"
            return False
        return True

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step when user initializes a integration."""
        return self.async_show_menu(
            step_id="user", menu_options=["network", "usbselect"]
        )

    async def async_step_network(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle network step."""
        if user_input is not None:
            self._title = "Velbus Network"
            if user_input[CONF_TLS]:
                self._device = "tls://"
            else:
                self._device = ""
            if CONF_PASSWORD in user_input and user_input[CONF_PASSWORD] != "":
                self._device += f"{user_input[CONF_PASSWORD]}@"
            self._device += f"{user_input[CONF_HOST]}:{user_input[CONF_PORT]}"
            self._async_abort_entries_match({CONF_PORT: self._device})
            if await self._test_connection():
                return self._create_device()
        else:
            user_input = {
                CONF_TLS: True,
                CONF_PORT: 27015,
            }

        return self.async_show_form(
            step_id="network",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(
                    {
                        vol.Required(CONF_TLS): bool,
                        vol.Required(CONF_HOST): str,
                        vol.Required(CONF_PORT): int,
                        vol.Optional(CONF_PASSWORD): str,
                    }
                ),
                suggested_values=user_input,
            ),
            errors=self._errors,
        )

    async def async_step_usbselect(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle usb select step."""
        ports = await self.hass.async_add_executor_job(serial.tools.list_ports.comports)
        list_of_ports = [
            f"{p}{', s/n: ' + p.serial_number if p.serial_number else ''}"
            + (f" - {p.manufacturer}" if p.manufacturer else "")
            for p in ports
        ]

        if user_input is not None:
            self._title = "Velbus USB"
            self._device = ports[list_of_ports.index(user_input[CONF_PORT])].device
            self._async_abort_entries_match({CONF_PORT: self._device})
            if await self._test_connection():
                return self._create_device()
        else:
            user_input = {}
            user_input[CONF_PORT] = ""

        return self.async_show_form(
            step_id="usbselect",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema({vol.Required(CONF_PORT): vol.In(list_of_ports)}),
                suggested_values=user_input,
            ),
            errors=self._errors,
        )

    async def async_step_usb(self, discovery_info: UsbServiceInfo) -> ConfigFlowResult:
        """Handle USB Discovery."""
        await self.async_set_unique_id(discovery_info.serial_number)
        self._device = discovery_info.device
        self._title = "Velbus USB"
        self._async_abort_entries_match({CONF_PORT: self._device})
        if not await self._test_connection():
            return self.async_abort(reason="cannot_connect")
        # call the config step
        self._set_confirm_only()
        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle Discovery confirmation."""
        if user_input is not None:
            return self._create_device()

        return self.async_show_form(
            step_id="discovery_confirm",
            description_placeholders={CONF_NAME: self._title},
        )
