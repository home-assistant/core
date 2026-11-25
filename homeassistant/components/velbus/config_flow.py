"""Config flow for the Velbus platform."""

from collections.abc import Mapping
from ipaddress import ip_address
from pathlib import Path
import shutil
from typing import Any, Final, override
from urllib.parse import urlparse

import probatio
import velbusaio.controller
from velbusaio.exceptions import VelbusAuthenticationFailed, VelbusConnectionFailed
from velbusaio.vlp_reader import VlpFile

from homeassistant.components.file_upload import process_uploaded_file
from homeassistant.config_entries import (
    SOURCE_RECONFIGURE,
    ConfigFlow,
    ConfigFlowResult,
)
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_HOST, CONF_PASSWORD, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.hassio import is_hassio
from homeassistant.helpers.service_info.usb import UsbServiceInfo

from .const import CONF_TLS, CONF_VLP_FILE, DOMAIN, MANAGER_DEFAULT_PORT

STORAGE_PATH: Final = ".storage/velbus.{key}.vlp"


def format_manager_dsn(host: str, port: int) -> str:
    """Build a manager:// DSN, bracketing IPv6 literals when required."""
    host = host.strip()
    if host.startswith("[") and host.endswith("]"):
        bracketed_host = host
    elif _host_requires_brackets(host):
        bracketed_host = f"[{host}]"
    else:
        bracketed_host = host
    return f"manager://{bracketed_host}:{port}"


def manager_dsn_to_host_port(dsn: str) -> tuple[str, int]:
    """Parse host and port from a manager:// DSN."""
    parts = urlparse(dsn)
    return parts.hostname or "", parts.port or MANAGER_DEFAULT_PORT


def _host_requires_brackets(host: str) -> bool:
    """Return whether *host* is an IPv6 literal that must be bracketed in the DSN."""
    try:
        return ip_address(host).version == 6
    except ValueError:
        return False


class InvalidVlpFile(HomeAssistantError):
    """Error to indicate that the uploaded file is not a valid VLP file."""


class VelbusConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 3
    MINOR_VERSION = 2

    def __init__(self) -> None:
        """Initialize the velbus config flow."""
        self._device: str = ""
        self._vlp_file: str | None = None
        self._title: str = ""
        self._access_token: str | None = None

    def _create_device(self) -> ConfigFlowResult:
        """Create an entry async."""
        data: dict[str, Any] = {CONF_PORT: self._device, CONF_VLP_FILE: self._vlp_file}
        if self._access_token:
            data[CONF_ACCESS_TOKEN] = self._access_token
        return self.async_create_entry(
            title=self._title,
            data=data,
        )

    async def _test_connection(self, *, error_field: str = CONF_HOST) -> str | None:
        """Try to connect to the velbus with the port specified."""
        use_manager = self._device.startswith("manager://")
        try:
            controller = velbusaio.controller.Velbus(
                self._device,
                session=async_get_clientsession(self.hass) if use_manager else None,
                access_token=self._access_token,
            )
            await controller.connect()
            await controller.stop()
        except VelbusAuthenticationFailed:
            return CONF_ACCESS_TOKEN
        except VelbusConnectionFailed:
            return error_field
        return None

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step when user initializes a integration."""
        return self.async_show_menu(
            step_id="user", menu_options=["network", "manager", "usbselect"]
        )

    async def async_step_network(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle network step."""
        step_errors: dict[str, str] = {}
        if user_input is not None:
            self._title = "Velbus Network"
            self._access_token = None
            if user_input[CONF_TLS]:
                self._device = "tls://"
            else:
                self._device = ""
            if CONF_PASSWORD in user_input and user_input[CONF_PASSWORD] != "":
                self._device += f"{user_input[CONF_PASSWORD]}@"
            self._device += f"{user_input[CONF_HOST]}:{user_input[CONF_PORT]}"
            if self.source != SOURCE_RECONFIGURE:
                self._async_abort_entries_match({CONF_PORT: self._device})
            if connect_error := await self._test_connection():
                step_errors[connect_error] = (
                    "invalid_access_token"
                    if connect_error == CONF_ACCESS_TOKEN
                    else "cannot_connect"
                )
            else:
                return await self.async_step_vlp()
        elif self.source == SOURCE_RECONFIGURE:
            current = self._get_reconfigure_entry().data.get(CONF_PORT, "")
            tls = current.startswith("tls://")
            current = current.removeprefix("tls://")
            if "@" in current:
                password, host_port = current.split("@", 1)
            else:
                password = ""
                host_port = current
            host, _, port = host_port.rpartition(":")
            user_input = {
                CONF_TLS: tls,
                CONF_HOST: host,
                CONF_PORT: int(port) if port.isdigit() else 27015,
            }
            if password:
                user_input[CONF_PASSWORD] = password
        else:
            user_input = {
                CONF_TLS: True,
                CONF_PORT: 27015,
            }

        return self.async_show_form(
            step_id="network",
            data_schema=self.add_suggested_values_to_schema(
                probatio.Schema(
                    {
                        probatio.Required(CONF_TLS): bool,
                        probatio.Required(CONF_HOST): str,
                        probatio.Required(CONF_PORT): int,
                        probatio.Optional(probatio.Secret(CONF_PASSWORD)): str,
                    }
                ),
                suggested_values=user_input,
            ),
            errors=step_errors,
        )

    async def async_step_manager(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle Velbus Manager connection."""
        step_errors: dict[str, str] = {}
        if user_input is not None:
            self._title = "Velbus Manager"
            host = user_input[CONF_HOST]
            port = user_input[CONF_PORT]
            self._device = format_manager_dsn(host, port)
            if self.source == SOURCE_RECONFIGURE:
                if CONF_ACCESS_TOKEN in user_input:
                    self._access_token = user_input[CONF_ACCESS_TOKEN] or None
            else:
                self._access_token = user_input.get(CONF_ACCESS_TOKEN) or None
            if connect_error := await self._test_connection():
                step_errors[connect_error] = (
                    "invalid_access_token"
                    if connect_error == CONF_ACCESS_TOKEN
                    else "cannot_connect"
                )
            else:
                self._async_abort_entries_match({CONF_PORT: self._device})
                self._vlp_file = None
                if self.source == SOURCE_RECONFIGURE:
                    old_entry = self._get_reconfigure_entry()
                    data = dict(old_entry.data)
                    data[CONF_PORT] = self._device
                    data[CONF_VLP_FILE] = None
                    if self._access_token:
                        data[CONF_ACCESS_TOKEN] = self._access_token
                    else:
                        data.pop(CONF_ACCESS_TOKEN, None)
                    return self.async_update_reload_and_abort(old_entry, data=data)
                return self._create_device()
        elif self.source == SOURCE_RECONFIGURE:
            reconfigure_entry = self._get_reconfigure_entry()
            current = reconfigure_entry.data.get(CONF_PORT, "")
            host, port = manager_dsn_to_host_port(current)
            self._access_token = reconfigure_entry.data.get(CONF_ACCESS_TOKEN)
            user_input = {
                CONF_HOST: host,
                CONF_PORT: port,
            }
            if self._access_token:
                user_input[CONF_ACCESS_TOKEN] = self._access_token
        else:
            user_input = {
                CONF_HOST: "manager" if is_hassio(self.hass) else "127.0.0.1",
                CONF_PORT: MANAGER_DEFAULT_PORT,
            }

        return self.async_show_form(
            step_id="manager",
            data_schema=self.add_suggested_values_to_schema(
                probatio.Schema(
                    {
                        probatio.Required(CONF_HOST): str,
                        probatio.Required(CONF_PORT): int,
                        probatio.Optional(probatio.Secret(CONF_ACCESS_TOKEN)): str,
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

        if user_input is not None:
            self._title = "Velbus USB"
            self._access_token = None
            self._device = user_input[CONF_PORT]
            self._async_abort_entries_match({CONF_PORT: self._device})
            if connect_error := await self._test_connection(error_field=CONF_PORT):
                step_errors[connect_error] = "cannot_connect"
            else:
                return await self.async_step_vlp()
        else:
            user_input = {}
            user_input[CONF_PORT] = ""

        return self.async_show_form(
            step_id="usbselect",
            data_schema=self.add_suggested_values_to_schema(
                probatio.Schema(
                    {probatio.Required(CONF_PORT): selector.SerialPortSelector()}
                ),
                suggested_values=user_input,
            ),
            errors=step_errors,
        )

    @override
    async def async_step_usb(self, discovery_info: UsbServiceInfo) -> ConfigFlowResult:
        """Handle USB Discovery."""
        await self.async_set_unique_id(discovery_info.serial_number)
        self._device = discovery_info.device
        self._title = "Velbus USB"
        self._async_abort_entries_match({CONF_PORT: self._device})
        if await self._test_connection(error_field=CONF_PORT):
            return self.async_abort(reason="cannot_connect")
        # call the config step
        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle Discovery confirmation."""
        if user_input is not None:
            return self._create_device()

        return self.async_show_form(
            step_id="discovery_confirm",
            description_placeholders={"name": self._title},
        )

    async def _validate_vlp_file(self, file_path: str) -> None:
        """Validate VLP file and raise exception if invalid."""
        vlpfile = VlpFile(file_path)
        await vlpfile.read()
        if not vlpfile.get():
            raise InvalidVlpFile(
                translation_domain=DOMAIN,
                translation_key="no_modules",
            )

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
                except InvalidVlpFile as exc:
                    if exc.translation_key is not None:
                        step_errors[CONF_VLP_FILE] = exc.translation_key
            if self.source == SOURCE_RECONFIGURE:
                old_entry = self._get_reconfigure_entry()
                return self.async_update_reload_and_abort(
                    old_entry,
                    data={
                        CONF_VLP_FILE: self._vlp_file,
                        CONF_PORT: self._device,
                    },
                )
            if not step_errors:
                return self._create_device()

        return self.async_show_form(
            step_id="vlp",
            data_schema=self.add_suggested_values_to_schema(
                probatio.Schema(
                    {
                        probatio.Optional(CONF_VLP_FILE): selector.FileSelector(
                            config=selector.FileSelectorConfig(accept=".vlp")
                        ),
                    }
                ),
                suggested_values=user_input,
            ),
            errors=step_errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Reauthenticate a Velbus Manager entry."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Update the Velbus Manager access token."""
        errors: dict[str, str] = {}
        reauth_entry = self._get_reauth_entry()
        self._device = reauth_entry.data[CONF_PORT]

        if user_input is not None:
            token = user_input.get(CONF_ACCESS_TOKEN)
            self._access_token = token or None
            if connect_error := await self._test_connection(error_field="base"):
                errors[connect_error] = (
                    "invalid_access_token"
                    if connect_error == CONF_ACCESS_TOKEN
                    else "cannot_connect"
                )
            else:
                data = dict(reauth_entry.data)
                if self._access_token:
                    data[CONF_ACCESS_TOKEN] = self._access_token
                else:
                    data.pop(CONF_ACCESS_TOKEN, None)
                return self.async_update_reload_and_abort(reauth_entry, data=data)

        suggested_input: dict[str, Any] = {}
        if user_input is not None and CONF_ACCESS_TOKEN in user_input:
            suggested_input[CONF_ACCESS_TOKEN] = user_input[CONF_ACCESS_TOKEN]
        elif token := reauth_entry.data.get(CONF_ACCESS_TOKEN):
            suggested_input[CONF_ACCESS_TOKEN] = token

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=self.add_suggested_values_to_schema(
                probatio.Schema(
                    {
                        probatio.Optional(probatio.Secret(CONF_ACCESS_TOKEN)): str,
                    }
                ),
                suggested_values=suggested_input,
            ),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration."""
        if (
            self._get_reconfigure_entry()
            .data.get(CONF_PORT, "")
            .startswith("manager://")
        ):
            return await self.async_step_manager(user_input)
        return await self.async_step_network(user_input)


def save_uploaded_vlp_file(hass: HomeAssistant, uploaded_file_id: str) -> str:
    """Validate the uploaded file and move it to the storage directory.

    Blocking function needs to be called in executor.
    """

    with process_uploaded_file(hass, uploaded_file_id) as file:
        dest_path = Path(hass.config.path(STORAGE_PATH.format(key=uploaded_file_id)))
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(file, dest_path)
        return str(dest_path)
