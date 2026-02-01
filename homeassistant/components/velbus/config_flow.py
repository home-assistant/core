"""Config flow for the Velbus platform."""

from __future__ import annotations

from pathlib import Path
import shutil
from typing import Any, Final

import serial.tools.list_ports
import velbusaio.controller
from velbusaio.exceptions import VelbusConnectionFailed
from velbusaio.vlp_reader import VlpFile
import voluptuous as vol

from homeassistant.components.file_upload import process_uploaded_file
from homeassistant.config_entries import (
    SOURCE_RECONFIGURE,
    ConfigFlow,
    ConfigFlowResult,
)
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PASSWORD, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import selector
from homeassistant.helpers.service_info.usb import UsbServiceInfo

from .const import CONF_TLS, CONF_VLP_FILE, DOMAIN

STORAGE_PATH: Final = ".storage/velbus.{key}.vlp"


class InvalidVlpFile(HomeAssistantError):
    """Error to indicate that the uploaded file is not a valid VLP file."""


class VelbusConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 2
    MINOR_VERSION = 2

    def __init__(self) -> None:
        """Initialize the velbus config flow."""
        self._device: str = ""
        self._vlp_file: str | None = None
        self._title: str = ""

    def _create_device(self) -> ConfigFlowResult:
        """Create an entry async."""
        return self.async_create_entry(
            title=self._title,
            data={CONF_PORT: self._device, CONF_VLP_FILE: self._vlp_file},
        )

    async def _test_connection(self) -> bool:
        """Try to connect to the velbus with the port specified."""
        try:
            controller = velbusaio.controller.Velbus(self._device)
            await controller.connect()
            await controller.stop()
        except VelbusConnectionFailed:
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
        step_errors: dict[str, str] = {}
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
                return await self.async_step_vlp()
            step_errors[CONF_HOST] = "cannot_connect"
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
            errors=step_errors,
        )

    async def async_step_usbselect(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle usb select step."""
        step_errors: dict[str, str] = {}
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
                return await self.async_step_vlp()
            step_errors[CONF_PORT] = "cannot_connect"
        else:
            user_input = {}
            user_input[CONF_PORT] = ""

        return self.async_show_form(
            step_id="usbselect",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema({vol.Required(CONF_PORT): vol.In(list_of_ports)}),
                suggested_values=user_input,
            ),
            errors=step_errors,
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

    async def _validate_vlp_file(self, file_path: str) -> None:
        """Validate VLP file and raise exception if invalid."""
        vlpfile = VlpFile(file_path)
        await vlpfile.read()
        if not vlpfile.get():
            raise InvalidVlpFile("no_modules")

    async def async_step_vlp(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step when user wants to use the VLP file."""
        step_errors: dict[str, str] = {}
        if user_input is not None:
            if CONF_VLP_FILE not in user_input or user_input[CONF_VLP_FILE] == "":
                # The VLP file is optional, so allow skipping it
                self._vlp_file = None
            else:
                try:
                    # handle the file upload
                    self._vlp_file = await self.hass.async_add_executor_job(
                        save_uploaded_vlp_file, self.hass, user_input[CONF_VLP_FILE]
                    )
                    # validate it
                    await self._validate_vlp_file(self._vlp_file)
                except InvalidVlpFile as e:
                    step_errors[CONF_VLP_FILE] = str(e)
            if self.source == SOURCE_RECONFIGURE:
                old_entry = self._get_reconfigure_entry()
                return self.async_update_reload_and_abort(
                    old_entry,
                    data={
                        CONF_VLP_FILE: self._vlp_file,
                        CONF_PORT: old_entry.data.get(CONF_PORT),
                    },
                )
            if not step_errors:
                return self._create_device()

        return self.async_show_form(
            step_id="vlp",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(
                    {
                        vol.Optional(CONF_VLP_FILE): selector.FileSelector(
                            config=selector.FileSelectorConfig(accept=".vlp")
                        ),
                    }
                ),
                suggested_values=user_input,
            ),
            errors=step_errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration."""
        return await self.async_step_vlp()


def save_uploaded_vlp_file(hass: HomeAssistant, uploaded_file_id: str) -> str:
    """Validate the uploaded file and move it to the storage directory.

    Blocking function needs to be called in executor.
    """

    with process_uploaded_file(hass, uploaded_file_id) as file:
        dest_path = Path(hass.config.path(STORAGE_PATH.format(key=uploaded_file_id)))
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(file, dest_path)
        return str(dest_path)
