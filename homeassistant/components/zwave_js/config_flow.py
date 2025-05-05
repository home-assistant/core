"""Config flow for Z-Wave JS integration."""

from __future__ import annotations

import asyncio
from datetime import datetime
import logging
from pathlib import Path
from typing import Any

import aiohttp
from awesomeversion import AwesomeVersion
from serial.tools import list_ports
import voluptuous as vol
from zwave_js_server.client import Client
from zwave_js_server.exceptions import FailedCommand
from zwave_js_server.model.driver import Driver
from zwave_js_server.version import VersionInfo, get_server_version

from homeassistant.components import usb
from homeassistant.components.hassio import (
    AddonError,
    AddonInfo,
    AddonManager,
    AddonState,
)
from homeassistant.config_entries import (
    SOURCE_USB,
    ConfigEntry,
    ConfigEntryState,
    ConfigFlow,
    ConfigFlowResult,
)
from homeassistant.const import CONF_NAME, CONF_URL
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import AbortFlow
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.hassio import is_hassio
from homeassistant.helpers.service_info.hassio import HassioServiceInfo
from homeassistant.helpers.service_info.usb import UsbServiceInfo
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo
from homeassistant.helpers.typing import VolDictType

from .addon import get_addon_manager
from .const import (
    ADDON_SLUG,
    CONF_ADDON_DEVICE,
    CONF_ADDON_EMULATE_HARDWARE,
    CONF_ADDON_LOG_LEVEL,
    CONF_ADDON_LR_S2_ACCESS_CONTROL_KEY,
    CONF_ADDON_LR_S2_AUTHENTICATED_KEY,
    CONF_ADDON_NETWORK_KEY,
    CONF_ADDON_S0_LEGACY_KEY,
    CONF_ADDON_S2_ACCESS_CONTROL_KEY,
    CONF_ADDON_S2_AUTHENTICATED_KEY,
    CONF_ADDON_S2_UNAUTHENTICATED_KEY,
    CONF_INTEGRATION_CREATED_ADDON,
    CONF_LR_S2_ACCESS_CONTROL_KEY,
    CONF_LR_S2_AUTHENTICATED_KEY,
    CONF_S0_LEGACY_KEY,
    CONF_S2_ACCESS_CONTROL_KEY,
    CONF_S2_AUTHENTICATED_KEY,
    CONF_S2_UNAUTHENTICATED_KEY,
    CONF_USB_PATH,
    CONF_USE_ADDON,
    DATA_CLIENT,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

DEFAULT_URL = "ws://localhost:3000"
TITLE = "Z-Wave JS"

ADDON_SETUP_TIMEOUT = 5
ADDON_SETUP_TIMEOUT_ROUNDS = 40
CONF_EMULATE_HARDWARE = "emulate_hardware"
CONF_LOG_LEVEL = "log_level"
SERVER_VERSION_TIMEOUT = 10

ADDON_LOG_LEVELS = {
    "error": "Error",
    "warn": "Warn",
    "info": "Info",
    "verbose": "Verbose",
    "debug": "Debug",
    "silly": "Silly",
}
ADDON_USER_INPUT_MAP = {
    CONF_ADDON_DEVICE: CONF_USB_PATH,
    CONF_ADDON_S0_LEGACY_KEY: CONF_S0_LEGACY_KEY,
    CONF_ADDON_S2_ACCESS_CONTROL_KEY: CONF_S2_ACCESS_CONTROL_KEY,
    CONF_ADDON_S2_AUTHENTICATED_KEY: CONF_S2_AUTHENTICATED_KEY,
    CONF_ADDON_S2_UNAUTHENTICATED_KEY: CONF_S2_UNAUTHENTICATED_KEY,
    CONF_ADDON_LR_S2_ACCESS_CONTROL_KEY: CONF_LR_S2_ACCESS_CONTROL_KEY,
    CONF_ADDON_LR_S2_AUTHENTICATED_KEY: CONF_LR_S2_AUTHENTICATED_KEY,
    CONF_ADDON_LOG_LEVEL: CONF_LOG_LEVEL,
    CONF_ADDON_EMULATE_HARDWARE: CONF_EMULATE_HARDWARE,
}

ON_SUPERVISOR_SCHEMA = vol.Schema({vol.Optional(CONF_USE_ADDON, default=True): bool})
MIN_MIGRATION_SDK_VERSION = AwesomeVersion("6.61")


def get_manual_schema(user_input: dict[str, Any]) -> vol.Schema:
    """Return a schema for the manual step."""
    default_url = user_input.get(CONF_URL, DEFAULT_URL)
    return vol.Schema({vol.Required(CONF_URL, default=default_url): str})


def get_on_supervisor_schema(user_input: dict[str, Any]) -> vol.Schema:
    """Return a schema for the on Supervisor step."""
    default_use_addon = user_input[CONF_USE_ADDON]
    return vol.Schema({vol.Optional(CONF_USE_ADDON, default=default_use_addon): bool})


async def validate_input(hass: HomeAssistant, user_input: dict) -> VersionInfo:
    """Validate if the user input allows us to connect."""
    ws_address = user_input[CONF_URL]

    if not ws_address.startswith(("ws://", "wss://")):
        raise InvalidInput("invalid_ws_url")

    try:
        return await async_get_version_info(hass, ws_address)
    except CannotConnect as err:
        raise InvalidInput("cannot_connect") from err


async def async_get_version_info(hass: HomeAssistant, ws_address: str) -> VersionInfo:
    """Return Z-Wave JS version info."""
    try:
        async with asyncio.timeout(SERVER_VERSION_TIMEOUT):
            version_info: VersionInfo = await get_server_version(
                ws_address, async_get_clientsession(hass)
            )
    except (TimeoutError, aiohttp.ClientError) as err:
        # We don't want to spam the log if the add-on isn't started
        # or takes a long time to start.
        _LOGGER.debug("Failed to connect to Z-Wave JS server: %s", err)
        raise CannotConnect from err

    return version_info


def get_usb_ports() -> dict[str, str]:
    """Return a dict of USB ports and their friendly names."""
    ports = list_ports.comports()
    port_descriptions = {}
    for port in ports:
        vid: str | None = None
        pid: str | None = None
        if port.vid is not None and port.pid is not None:
            usb_device = usb.usb_device_from_port(port)
            vid = usb_device.vid
            pid = usb_device.pid
        dev_path = usb.get_serial_by_id(port.device)
        human_name = usb.human_readable_device_name(
            dev_path,
            port.serial_number,
            port.manufacturer,
            port.description,
            vid,
            pid,
        )
        port_descriptions[dev_path] = human_name
    return port_descriptions


async def async_get_usb_ports(hass: HomeAssistant) -> dict[str, str]:
    """Return a dict of USB ports and their friendly names."""
    return await hass.async_add_executor_job(get_usb_ports)


class ZWaveJSConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Z-Wave JS."""

    VERSION = 1

    _title: str

    def __init__(self) -> None:
        """Set up flow instance."""
        self.s0_legacy_key: str | None = None
        self.s2_access_control_key: str | None = None
        self.s2_authenticated_key: str | None = None
        self.s2_unauthenticated_key: str | None = None
        self.lr_s2_access_control_key: str | None = None
        self.lr_s2_authenticated_key: str | None = None
        self.usb_path: str | None = None
        self.ws_address: str | None = None
        self.restart_addon: bool = False
        # If we install the add-on we should uninstall it on entry remove.
        self.integration_created_addon = False
        self.install_task: asyncio.Task | None = None
        self.start_task: asyncio.Task | None = None
        self.version_info: VersionInfo | None = None
        self.original_addon_config: dict[str, Any] | None = None
        self.revert_reason: str | None = None
        self.backup_task: asyncio.Task | None = None
        self.restore_backup_task: asyncio.Task | None = None
        self.backup_data: bytes | None = None
        self.backup_filepath: str | None = None
        self.use_addon = False
        self._migrating = False
        self._reconfigure_config_entry: ConfigEntry | None = None
        self._usb_discovery = False

    async def async_step_install_addon(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Install Z-Wave JS add-on."""
        if not self.install_task:
            self.install_task = self.hass.async_create_task(self._async_install_addon())

        if not self.install_task.done():
            return self.async_show_progress(
                step_id="install_addon",
                progress_action="install_addon",
                progress_task=self.install_task,
            )

        try:
            await self.install_task
        except AddonError as err:
            _LOGGER.error(err)
            return self.async_show_progress_done(next_step_id="install_failed")
        finally:
            self.install_task = None

        self.integration_created_addon = True

        return self.async_show_progress_done(next_step_id="configure_addon")

    async def async_step_install_failed(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Add-on installation failed."""
        return self.async_abort(reason="addon_install_failed")

    async def async_step_start_addon(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Start Z-Wave JS add-on."""
        if not self.start_task:
            self.start_task = self.hass.async_create_task(self._async_start_addon())

        if not self.start_task.done():
            return self.async_show_progress(
                step_id="start_addon",
                progress_action="start_addon",
                progress_task=self.start_task,
            )

        try:
            await self.start_task
        except (CannotConnect, AddonError, AbortFlow) as err:
            _LOGGER.error(err)
            return self.async_show_progress_done(next_step_id="start_failed")
        finally:
            self.start_task = None

        return self.async_show_progress_done(next_step_id="finish_addon_setup")

    async def async_step_start_failed(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Add-on start failed."""
        if self._migrating:
            return self.async_abort(reason="addon_start_failed")
        if self._reconfigure_config_entry:
            return await self.async_revert_addon_config(reason="addon_start_failed")
        return self.async_abort(reason="addon_start_failed")

    async def _async_start_addon(self) -> None:
        """Start the Z-Wave JS add-on."""
        addon_manager: AddonManager = get_addon_manager(self.hass)
        self.version_info = None
        if self.restart_addon:
            await addon_manager.async_schedule_restart_addon()
        else:
            await addon_manager.async_schedule_start_addon()
        # Sleep some seconds to let the add-on start properly before connecting.
        for _ in range(ADDON_SETUP_TIMEOUT_ROUNDS):
            await asyncio.sleep(ADDON_SETUP_TIMEOUT)
            try:
                if not self.ws_address:
                    discovery_info = await self._async_get_addon_discovery_info()
                    self.ws_address = (
                        f"ws://{discovery_info['host']}:{discovery_info['port']}"
                    )
                self.version_info = await async_get_version_info(
                    self.hass, self.ws_address
                )
            except (AbortFlow, CannotConnect) as err:
                _LOGGER.debug(
                    "Add-on not ready yet, waiting %s seconds: %s",
                    ADDON_SETUP_TIMEOUT,
                    err,
                )
            else:
                break
        else:
            raise CannotConnect("Failed to start Z-Wave JS add-on: timeout")

    async def async_step_configure_addon(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for config for Z-Wave JS add-on."""
        if self._reconfigure_config_entry:
            return await self.async_step_configure_addon_reconfigure(user_input)
        return await self.async_step_configure_addon_user(user_input)

    async def async_step_finish_addon_setup(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Prepare info needed to complete the config entry.

        Get add-on discovery info and server version info.
        Set unique id and abort if already configured.
        """
        if self._migrating:
            return await self.async_step_finish_addon_setup_migrate(user_input)
        if self._reconfigure_config_entry:
            return await self.async_step_finish_addon_setup_reconfigure(user_input)
        return await self.async_step_finish_addon_setup_user(user_input)

    async def _async_get_addon_info(self) -> AddonInfo:
        """Return and cache Z-Wave JS add-on info."""
        addon_manager: AddonManager = get_addon_manager(self.hass)
        try:
            addon_info: AddonInfo = await addon_manager.async_get_addon_info()
        except AddonError as err:
            _LOGGER.error(err)
            raise AbortFlow("addon_info_failed") from err

        return addon_info

    async def _async_set_addon_config(self, config_updates: dict) -> None:
        """Set Z-Wave JS add-on config."""
        addon_info = await self._async_get_addon_info()
        addon_config = addon_info.options

        new_addon_config = addon_config | config_updates

        if new_addon_config == addon_config:
            return

        if addon_info.state == AddonState.RUNNING:
            self.restart_addon = True
        # Copy the add-on config to keep the objects separate.
        self.original_addon_config = dict(addon_config)
        # Remove legacy network_key
        new_addon_config.pop(CONF_ADDON_NETWORK_KEY, None)
        addon_manager: AddonManager = get_addon_manager(self.hass)
        try:
            await addon_manager.async_set_addon_options(new_addon_config)
        except AddonError as err:
            _LOGGER.error(err)
            raise AbortFlow("addon_set_config_failed") from err

    async def _async_install_addon(self) -> None:
        """Install the Z-Wave JS add-on."""
        addon_manager: AddonManager = get_addon_manager(self.hass)
        await addon_manager.async_schedule_install_addon()

    async def _async_get_addon_discovery_info(self) -> dict:
        """Return add-on discovery info."""
        addon_manager: AddonManager = get_addon_manager(self.hass)
        try:
            discovery_info_config = await addon_manager.async_get_addon_discovery_info()
        except AddonError as err:
            _LOGGER.error(err)
            raise AbortFlow("addon_get_discovery_info_failed") from err

        return discovery_info_config

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if is_hassio(self.hass):
            return await self.async_step_on_supervisor()

        return await self.async_step_manual()

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm if we are migrating adapters or just re-configuring."""
        self._reconfigure_config_entry = self._get_reconfigure_entry()
        return self.async_show_menu(
            step_id="reconfigure",
            menu_options=[
                "intent_reconfigure",
                "intent_migrate",
            ],
        )

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle zeroconf discovery."""
        home_id = str(discovery_info.properties["homeId"])
        await self.async_set_unique_id(home_id)
        self._abort_if_unique_id_configured()
        self.ws_address = f"ws://{discovery_info.host}:{discovery_info.port}"
        self.context.update({"title_placeholders": {CONF_NAME: home_id}})
        return await self.async_step_zeroconf_confirm()

    async def async_step_zeroconf_confirm(
        self, user_input: dict | None = None
    ) -> ConfigFlowResult:
        """Confirm the setup."""
        if user_input is not None:
            return await self.async_step_manual({CONF_URL: self.ws_address})

        assert self.ws_address
        assert self.unique_id
        return self.async_show_form(
            step_id="zeroconf_confirm",
            description_placeholders={
                "home_id": self.unique_id,
                CONF_URL: self.ws_address[5:],
            },
        )

    async def async_step_usb(self, discovery_info: UsbServiceInfo) -> ConfigFlowResult:
        """Handle USB Discovery."""
        if not is_hassio(self.hass):
            return self.async_abort(reason="discovery_requires_supervisor")
        if any(
            flow
            for flow in self._async_in_progress()
            if flow["context"].get("source") != SOURCE_USB
        ):
            # Allow multiple USB discovery flows to be in progress.
            # Migration requires more than one USB stick to be connected,
            # which can cause more than one discovery flow to be in progress,
            # at least for a short time.
            return self.async_abort(reason="already_in_progress")
        if current_config_entries := self._async_current_entries(include_ignore=False):
            config_entry = next(
                (
                    entry
                    for entry in current_config_entries
                    if entry.data.get(CONF_USE_ADDON)
                ),
                None,
            )
            if not config_entry:
                return self.async_abort(reason="addon_required")

        vid = discovery_info.vid
        pid = discovery_info.pid
        serial_number = discovery_info.serial_number
        manufacturer = discovery_info.manufacturer
        description = discovery_info.description
        # Zooz uses this vid/pid, but so do 2652 sticks
        if vid == "10C4" and pid == "EA60" and description and "2652" in description:
            return self.async_abort(reason="not_zwave_device")

        addon_info = await self._async_get_addon_info()
        if (
            addon_info.state not in (AddonState.NOT_INSTALLED, AddonState.INSTALLING)
            and addon_info.options.get(CONF_ADDON_DEVICE) == discovery_info.device
        ):
            return self.async_abort(reason="already_configured")

        await self.async_set_unique_id(
            f"{vid}:{pid}_{serial_number}_{manufacturer}_{description}"
        )
        # We don't need to check if the unique_id is already configured
        # since we will update the unique_id before finishing the flow.
        # The unique_id set above is just a temporary value to avoid
        # duplicate discovery flows.
        dev_path = discovery_info.device
        self.usb_path = dev_path
        if manufacturer == "Nabu Casa" and description == "ZWA-2 - Nabu Casa ZWA-2":
            title = "Home Assistant Connect ZWA-2"
        else:
            human_name = usb.human_readable_device_name(
                dev_path,
                serial_number,
                manufacturer,
                description,
                vid,
                pid,
            )
            title = human_name.split(" - ")[0].strip()
        self.context["title_placeholders"] = {CONF_NAME: title}
        self._title = title
        return await self.async_step_usb_confirm()

    async def async_step_usb_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle USB Discovery confirmation."""
        if user_input is None:
            return self.async_show_form(
                step_id="usb_confirm",
                description_placeholders={CONF_NAME: self._title},
            )

        self._usb_discovery = True
        if current_config_entries := self._async_current_entries(include_ignore=False):
            self._reconfigure_config_entry = next(
                (
                    entry
                    for entry in current_config_entries
                    if entry.data.get(CONF_USE_ADDON)
                ),
                None,
            )
            if not self._reconfigure_config_entry:
                return self.async_abort(reason="addon_required")
            return await self.async_step_intent_migrate()

        return await self.async_step_on_supervisor({CONF_USE_ADDON: True})

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a manual configuration."""
        if user_input is None:
            return self.async_show_form(
                step_id="manual", data_schema=get_manual_schema({})
            )

        errors = {}

        try:
            version_info = await validate_input(self.hass, user_input)
        except InvalidInput as err:
            errors["base"] = err.error
        except Exception:
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            await self.async_set_unique_id(
                str(version_info.home_id), raise_on_progress=False
            )
            # Make sure we disable any add-on handling
            # if the controller is reconfigured in a manual step.
            self._abort_if_unique_id_configured(
                updates={
                    **user_input,
                    CONF_USE_ADDON: False,
                    CONF_INTEGRATION_CREATED_ADDON: False,
                }
            )
            self.ws_address = user_input[CONF_URL]
            return self._async_create_entry_from_vars()

        return self.async_show_form(
            step_id="manual", data_schema=get_manual_schema(user_input), errors=errors
        )

    async def async_step_hassio(
        self, discovery_info: HassioServiceInfo
    ) -> ConfigFlowResult:
        """Receive configuration from add-on discovery info.

        This flow is triggered by the Z-Wave JS add-on.
        """
        if self._async_in_progress():
            return self.async_abort(reason="already_in_progress")

        if discovery_info.slug != ADDON_SLUG:
            return self.async_abort(reason="not_zwave_js_addon")

        self.ws_address = (
            f"ws://{discovery_info.config['host']}:{discovery_info.config['port']}"
        )
        try:
            version_info = await async_get_version_info(self.hass, self.ws_address)
        except CannotConnect:
            return self.async_abort(reason="cannot_connect")

        await self.async_set_unique_id(str(version_info.home_id))
        self._abort_if_unique_id_configured(updates={CONF_URL: self.ws_address})

        return await self.async_step_hassio_confirm()

    async def async_step_hassio_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm the add-on discovery."""
        if user_input is not None:
            return await self.async_step_on_supervisor(
                user_input={CONF_USE_ADDON: True}
            )

        return self.async_show_form(step_id="hassio_confirm")

    async def async_step_on_supervisor(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle logic when on Supervisor host."""
        if user_input is None:
            return self.async_show_form(
                step_id="on_supervisor", data_schema=ON_SUPERVISOR_SCHEMA
            )
        if not user_input[CONF_USE_ADDON]:
            return await self.async_step_manual()

        self.use_addon = True

        addon_info = await self._async_get_addon_info()

        if addon_info.state == AddonState.RUNNING:
            addon_config = addon_info.options
            self.usb_path = addon_config[CONF_ADDON_DEVICE]
            self.s0_legacy_key = addon_config.get(CONF_ADDON_S0_LEGACY_KEY, "")
            self.s2_access_control_key = addon_config.get(
                CONF_ADDON_S2_ACCESS_CONTROL_KEY, ""
            )
            self.s2_authenticated_key = addon_config.get(
                CONF_ADDON_S2_AUTHENTICATED_KEY, ""
            )
            self.s2_unauthenticated_key = addon_config.get(
                CONF_ADDON_S2_UNAUTHENTICATED_KEY, ""
            )
            self.lr_s2_access_control_key = addon_config.get(
                CONF_ADDON_LR_S2_ACCESS_CONTROL_KEY, ""
            )
            self.lr_s2_authenticated_key = addon_config.get(
                CONF_ADDON_LR_S2_AUTHENTICATED_KEY, ""
            )
            return await self.async_step_finish_addon_setup_user()

        if addon_info.state == AddonState.NOT_RUNNING:
            return await self.async_step_configure_addon_user()

        return await self.async_step_install_addon()

    async def async_step_configure_addon_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for config for Z-Wave JS add-on."""
        addon_info = await self._async_get_addon_info()
        addon_config = addon_info.options

        if user_input is not None:
            self.s0_legacy_key = user_input[CONF_S0_LEGACY_KEY]
            self.s2_access_control_key = user_input[CONF_S2_ACCESS_CONTROL_KEY]
            self.s2_authenticated_key = user_input[CONF_S2_AUTHENTICATED_KEY]
            self.s2_unauthenticated_key = user_input[CONF_S2_UNAUTHENTICATED_KEY]
            self.lr_s2_access_control_key = user_input[CONF_LR_S2_ACCESS_CONTROL_KEY]
            self.lr_s2_authenticated_key = user_input[CONF_LR_S2_AUTHENTICATED_KEY]
            if not self._usb_discovery:
                self.usb_path = user_input[CONF_USB_PATH]

            addon_config_updates = {
                CONF_ADDON_DEVICE: self.usb_path,
                CONF_ADDON_S0_LEGACY_KEY: self.s0_legacy_key,
                CONF_ADDON_S2_ACCESS_CONTROL_KEY: self.s2_access_control_key,
                CONF_ADDON_S2_AUTHENTICATED_KEY: self.s2_authenticated_key,
                CONF_ADDON_S2_UNAUTHENTICATED_KEY: self.s2_unauthenticated_key,
                CONF_ADDON_LR_S2_ACCESS_CONTROL_KEY: self.lr_s2_access_control_key,
                CONF_ADDON_LR_S2_AUTHENTICATED_KEY: self.lr_s2_authenticated_key,
            }

            await self._async_set_addon_config(addon_config_updates)

            return await self.async_step_start_addon()

        usb_path = self.usb_path or addon_config.get(CONF_ADDON_DEVICE) or ""
        s0_legacy_key = addon_config.get(
            CONF_ADDON_S0_LEGACY_KEY, self.s0_legacy_key or ""
        )
        s2_access_control_key = addon_config.get(
            CONF_ADDON_S2_ACCESS_CONTROL_KEY, self.s2_access_control_key or ""
        )
        s2_authenticated_key = addon_config.get(
            CONF_ADDON_S2_AUTHENTICATED_KEY, self.s2_authenticated_key or ""
        )
        s2_unauthenticated_key = addon_config.get(
            CONF_ADDON_S2_UNAUTHENTICATED_KEY, self.s2_unauthenticated_key or ""
        )
        lr_s2_access_control_key = addon_config.get(
            CONF_ADDON_LR_S2_ACCESS_CONTROL_KEY, self.lr_s2_access_control_key or ""
        )
        lr_s2_authenticated_key = addon_config.get(
            CONF_ADDON_LR_S2_AUTHENTICATED_KEY, self.lr_s2_authenticated_key or ""
        )

        schema: VolDictType = {
            vol.Optional(CONF_S0_LEGACY_KEY, default=s0_legacy_key): str,
            vol.Optional(
                CONF_S2_ACCESS_CONTROL_KEY, default=s2_access_control_key
            ): str,
            vol.Optional(CONF_S2_AUTHENTICATED_KEY, default=s2_authenticated_key): str,
            vol.Optional(
                CONF_S2_UNAUTHENTICATED_KEY, default=s2_unauthenticated_key
            ): str,
            vol.Optional(
                CONF_LR_S2_ACCESS_CONTROL_KEY, default=lr_s2_access_control_key
            ): str,
            vol.Optional(
                CONF_LR_S2_AUTHENTICATED_KEY, default=lr_s2_authenticated_key
            ): str,
        }

        if not self._usb_discovery:
            try:
                ports = await async_get_usb_ports(self.hass)
            except OSError as err:
                _LOGGER.error("Failed to get USB ports: %s", err)
                return self.async_abort(reason="usb_ports_failed")

            schema = {
                vol.Required(CONF_USB_PATH, default=usb_path): vol.In(ports),
                **schema,
            }

        data_schema = vol.Schema(schema)

        return self.async_show_form(
            step_id="configure_addon_user", data_schema=data_schema
        )

    async def async_step_finish_addon_setup_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Prepare info needed to complete the config entry.

        Get add-on discovery info and server version info.
        Set unique id and abort if already configured.
        """
        if not self.ws_address:
            discovery_info = await self._async_get_addon_discovery_info()
            self.ws_address = f"ws://{discovery_info['host']}:{discovery_info['port']}"

        if not self.unique_id or self.source == SOURCE_USB:
            if not self.version_info:
                try:
                    self.version_info = await async_get_version_info(
                        self.hass, self.ws_address
                    )
                except CannotConnect as err:
                    raise AbortFlow("cannot_connect") from err

            await self.async_set_unique_id(
                str(self.version_info.home_id), raise_on_progress=False
            )

        self._abort_if_unique_id_configured(
            updates={
                CONF_URL: self.ws_address,
                CONF_USB_PATH: self.usb_path,
                CONF_S0_LEGACY_KEY: self.s0_legacy_key,
                CONF_S2_ACCESS_CONTROL_KEY: self.s2_access_control_key,
                CONF_S2_AUTHENTICATED_KEY: self.s2_authenticated_key,
                CONF_S2_UNAUTHENTICATED_KEY: self.s2_unauthenticated_key,
                CONF_LR_S2_ACCESS_CONTROL_KEY: self.lr_s2_access_control_key,
                CONF_LR_S2_AUTHENTICATED_KEY: self.lr_s2_authenticated_key,
            }
        )
        return self._async_create_entry_from_vars()

    @callback
    def _async_create_entry_from_vars(self) -> ConfigFlowResult:
        """Return a config entry for the flow."""
        # Abort any other flows that may be in progress
        for progress in self._async_in_progress():
            self.hass.config_entries.flow.async_abort(progress["flow_id"])

        return self.async_create_entry(
            title=TITLE,
            data={
                CONF_URL: self.ws_address,
                CONF_USB_PATH: self.usb_path,
                CONF_S0_LEGACY_KEY: self.s0_legacy_key,
                CONF_S2_ACCESS_CONTROL_KEY: self.s2_access_control_key,
                CONF_S2_AUTHENTICATED_KEY: self.s2_authenticated_key,
                CONF_S2_UNAUTHENTICATED_KEY: self.s2_unauthenticated_key,
                CONF_LR_S2_ACCESS_CONTROL_KEY: self.lr_s2_access_control_key,
                CONF_LR_S2_AUTHENTICATED_KEY: self.lr_s2_authenticated_key,
                CONF_USE_ADDON: self.use_addon,
                CONF_INTEGRATION_CREATED_ADDON: self.integration_created_addon,
            },
        )

    @callback
    def _async_update_entry(
        self, updates: dict[str, Any], *, schedule_reload: bool = True
    ) -> None:
        """Update the config entry with new data."""
        config_entry = self._reconfigure_config_entry
        assert config_entry is not None
        self.hass.config_entries.async_update_entry(
            config_entry, data=config_entry.data | updates
        )
        if schedule_reload:
            self.hass.config_entries.async_schedule_reload(config_entry.entry_id)

    async def async_step_intent_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if is_hassio(self.hass):
            return await self.async_step_on_supervisor_reconfigure()

        return await self.async_step_manual_reconfigure()

    async def async_step_intent_migrate(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm the user wants to reset their current controller."""
        config_entry = self._reconfigure_config_entry
        assert config_entry is not None
        if not self._usb_discovery and not config_entry.data.get(CONF_USE_ADDON):
            return self.async_abort(reason="addon_required")

        try:
            driver = self._get_driver()
        except AbortFlow:
            return self.async_abort(reason="config_entry_not_loaded")
        if (
            sdk_version := driver.controller.sdk_version
        ) is not None and sdk_version < MIN_MIGRATION_SDK_VERSION:
            _LOGGER.warning(
                "Migration from this controller that has SDK version %s "
                "is not supported. If possible, update the firmware "
                "of the controller to a firmware built using SDK version %s or higher",
                sdk_version,
                MIN_MIGRATION_SDK_VERSION,
            )
            return self.async_abort(
                reason="migration_low_sdk_version",
                description_placeholders={
                    "ok_sdk_version": str(MIN_MIGRATION_SDK_VERSION)
                },
            )

        if user_input is not None:
            self._migrating = True
            return await self.async_step_backup_nvm()

        return self.async_show_form(step_id="intent_migrate")

    async def async_step_backup_nvm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Backup the current network."""
        if self.backup_task is None:
            self.backup_task = self.hass.async_create_task(self._async_backup_network())

        if not self.backup_task.done():
            return self.async_show_progress(
                step_id="backup_nvm",
                progress_action="backup_nvm",
                progress_task=self.backup_task,
            )

        try:
            await self.backup_task
        except AbortFlow as err:
            _LOGGER.error(err)
            return self.async_show_progress_done(next_step_id="backup_failed")
        finally:
            self.backup_task = None

        return self.async_show_progress_done(next_step_id="instruct_unplug")

    async def async_step_restore_nvm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Restore the backup."""
        if self.restore_backup_task is None:
            self.restore_backup_task = self.hass.async_create_task(
                self._async_restore_network_backup()
            )

        if not self.restore_backup_task.done():
            return self.async_show_progress(
                step_id="restore_nvm",
                progress_action="restore_nvm",
                progress_task=self.restore_backup_task,
            )

        try:
            await self.restore_backup_task
        except AbortFlow as err:
            _LOGGER.error(err)
            return self.async_show_progress_done(next_step_id="restore_failed")
        finally:
            self.restore_backup_task = None

        return self.async_show_progress_done(next_step_id="migration_done")

    async def async_step_instruct_unplug(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Reset the current controller, and instruct the user to unplug it."""

        if user_input is not None:
            config_entry = self._reconfigure_config_entry
            assert config_entry is not None
            # Unload the config entry before stopping the add-on.
            await self.hass.config_entries.async_unload(config_entry.entry_id)
            if self.usb_path:
                # USB discovery was used, so the device is already known.
                await self._async_set_addon_config({CONF_ADDON_DEVICE: self.usb_path})
                return await self.async_step_start_addon()
            # Now that the old controller is gone, we can scan for serial ports again
            return await self.async_step_choose_serial_port()

        # reset the old controller
        try:
            await self._get_driver().async_hard_reset()
        except (AbortFlow, FailedCommand) as err:
            _LOGGER.error("Failed to reset controller: %s", err)
            return self.async_abort(reason="reset_failed")

        return self.async_show_form(
            step_id="instruct_unplug",
            description_placeholders={
                "file_path": str(self.backup_filepath),
            },
        )

    async def async_step_manual_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a manual configuration."""
        config_entry = self._reconfigure_config_entry
        assert config_entry is not None
        if user_input is None:
            return self.async_show_form(
                step_id="manual_reconfigure",
                data_schema=get_manual_schema({CONF_URL: config_entry.data[CONF_URL]}),
            )

        errors = {}

        try:
            version_info = await validate_input(self.hass, user_input)
        except InvalidInput as err:
            errors["base"] = err.error
        except Exception:
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            if config_entry.unique_id != str(version_info.home_id):
                return self.async_abort(reason="different_device")

            # Make sure we disable any add-on handling
            # if the controller is reconfigured in a manual step.
            self._async_update_entry(
                {
                    **user_input,
                    CONF_USE_ADDON: False,
                    CONF_INTEGRATION_CREATED_ADDON: False,
                }
            )

            return self.async_abort(reason="reconfigure_successful")

        return self.async_show_form(
            step_id="manual_reconfigure",
            data_schema=get_manual_schema(user_input),
            errors=errors,
        )

    async def async_step_on_supervisor_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle logic when on Supervisor host."""
        config_entry = self._reconfigure_config_entry
        assert config_entry is not None
        if user_input is None:
            return self.async_show_form(
                step_id="on_supervisor_reconfigure",
                data_schema=get_on_supervisor_schema(
                    {CONF_USE_ADDON: config_entry.data.get(CONF_USE_ADDON, True)}
                ),
            )

        if not user_input[CONF_USE_ADDON]:
            if config_entry.data.get(CONF_USE_ADDON):
                # Unload the config entry before stopping the add-on.
                await self.hass.config_entries.async_unload(config_entry.entry_id)
                addon_manager = get_addon_manager(self.hass)
                _LOGGER.debug("Stopping Z-Wave JS add-on")
                try:
                    await addon_manager.async_stop_addon()
                except AddonError as err:
                    _LOGGER.error(err)
                    self.hass.config_entries.async_schedule_reload(
                        config_entry.entry_id
                    )
                    raise AbortFlow("addon_stop_failed") from err
            return await self.async_step_manual_reconfigure()

        addon_info = await self._async_get_addon_info()

        if addon_info.state == AddonState.NOT_INSTALLED:
            return await self.async_step_install_addon()

        return await self.async_step_configure_addon_reconfigure()

    async def async_step_configure_addon_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for config for Z-Wave JS add-on."""
        addon_info = await self._async_get_addon_info()
        addon_config = addon_info.options

        if user_input is not None:
            self.s0_legacy_key = user_input[CONF_S0_LEGACY_KEY]
            self.s2_access_control_key = user_input[CONF_S2_ACCESS_CONTROL_KEY]
            self.s2_authenticated_key = user_input[CONF_S2_AUTHENTICATED_KEY]
            self.s2_unauthenticated_key = user_input[CONF_S2_UNAUTHENTICATED_KEY]
            self.lr_s2_access_control_key = user_input[CONF_LR_S2_ACCESS_CONTROL_KEY]
            self.lr_s2_authenticated_key = user_input[CONF_LR_S2_AUTHENTICATED_KEY]
            self.usb_path = user_input[CONF_USB_PATH]

            addon_config_updates = {
                CONF_ADDON_DEVICE: self.usb_path,
                CONF_ADDON_S0_LEGACY_KEY: self.s0_legacy_key,
                CONF_ADDON_S2_ACCESS_CONTROL_KEY: self.s2_access_control_key,
                CONF_ADDON_S2_AUTHENTICATED_KEY: self.s2_authenticated_key,
                CONF_ADDON_S2_UNAUTHENTICATED_KEY: self.s2_unauthenticated_key,
                CONF_ADDON_LR_S2_ACCESS_CONTROL_KEY: self.lr_s2_access_control_key,
                CONF_ADDON_LR_S2_AUTHENTICATED_KEY: self.lr_s2_authenticated_key,
                CONF_ADDON_LOG_LEVEL: user_input[CONF_LOG_LEVEL],
                CONF_ADDON_EMULATE_HARDWARE: user_input.get(
                    CONF_EMULATE_HARDWARE, False
                ),
            }

            await self._async_set_addon_config(addon_config_updates)

            if addon_info.state == AddonState.RUNNING and not self.restart_addon:
                return await self.async_step_finish_addon_setup_reconfigure()

            if (
                config_entry := self._reconfigure_config_entry
            ) and config_entry.data.get(CONF_USE_ADDON):
                # Disconnect integration before restarting add-on.
                await self.hass.config_entries.async_unload(config_entry.entry_id)

            return await self.async_step_start_addon()

        usb_path = addon_config.get(CONF_ADDON_DEVICE, self.usb_path or "")
        s0_legacy_key = addon_config.get(
            CONF_ADDON_S0_LEGACY_KEY, self.s0_legacy_key or ""
        )
        s2_access_control_key = addon_config.get(
            CONF_ADDON_S2_ACCESS_CONTROL_KEY, self.s2_access_control_key or ""
        )
        s2_authenticated_key = addon_config.get(
            CONF_ADDON_S2_AUTHENTICATED_KEY, self.s2_authenticated_key or ""
        )
        s2_unauthenticated_key = addon_config.get(
            CONF_ADDON_S2_UNAUTHENTICATED_KEY, self.s2_unauthenticated_key or ""
        )
        lr_s2_access_control_key = addon_config.get(
            CONF_ADDON_LR_S2_ACCESS_CONTROL_KEY, self.lr_s2_access_control_key or ""
        )
        lr_s2_authenticated_key = addon_config.get(
            CONF_ADDON_LR_S2_AUTHENTICATED_KEY, self.lr_s2_authenticated_key or ""
        )
        log_level = addon_config.get(CONF_ADDON_LOG_LEVEL, "info")
        emulate_hardware = addon_config.get(CONF_ADDON_EMULATE_HARDWARE, False)

        try:
            ports = await async_get_usb_ports(self.hass)
        except OSError as err:
            _LOGGER.error("Failed to get USB ports: %s", err)
            return self.async_abort(reason="usb_ports_failed")

        data_schema = vol.Schema(
            {
                vol.Required(CONF_USB_PATH, default=usb_path): vol.In(ports),
                vol.Optional(CONF_S0_LEGACY_KEY, default=s0_legacy_key): str,
                vol.Optional(
                    CONF_S2_ACCESS_CONTROL_KEY, default=s2_access_control_key
                ): str,
                vol.Optional(
                    CONF_S2_AUTHENTICATED_KEY, default=s2_authenticated_key
                ): str,
                vol.Optional(
                    CONF_S2_UNAUTHENTICATED_KEY, default=s2_unauthenticated_key
                ): str,
                vol.Optional(
                    CONF_LR_S2_ACCESS_CONTROL_KEY, default=lr_s2_access_control_key
                ): str,
                vol.Optional(
                    CONF_LR_S2_AUTHENTICATED_KEY, default=lr_s2_authenticated_key
                ): str,
                vol.Optional(CONF_LOG_LEVEL, default=log_level): vol.In(
                    ADDON_LOG_LEVELS
                ),
                vol.Optional(CONF_EMULATE_HARDWARE, default=emulate_hardware): bool,
            }
        )

        return self.async_show_form(
            step_id="configure_addon_reconfigure", data_schema=data_schema
        )

    async def async_step_choose_serial_port(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose a serial port."""
        if user_input is not None:
            self.usb_path = user_input[CONF_USB_PATH]
            await self._async_set_addon_config({CONF_ADDON_DEVICE: self.usb_path})
            return await self.async_step_start_addon()

        try:
            ports = await async_get_usb_ports(self.hass)
        except OSError as err:
            _LOGGER.error("Failed to get USB ports: %s", err)
            return self.async_abort(reason="usb_ports_failed")

        data_schema = vol.Schema(
            {
                vol.Required(CONF_USB_PATH): vol.In(ports),
            }
        )
        return self.async_show_form(
            step_id="choose_serial_port", data_schema=data_schema
        )

    async def async_step_backup_failed(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Backup failed."""
        return self.async_abort(reason="backup_failed")

    async def async_step_restore_failed(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Restore failed."""
        if user_input is not None:
            return await self.async_step_restore_nvm()

        return self.async_show_form(
            step_id="restore_failed",
            description_placeholders={
                "file_path": str(self.backup_filepath),
            },
        )

    async def async_step_migration_done(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Migration done."""
        return self.async_abort(reason="migration_successful")

    async def async_step_finish_addon_setup_migrate(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Prepare info needed to complete the config entry update."""
        ws_address = self.ws_address
        assert ws_address is not None
        version_info = self.version_info
        assert version_info is not None

        # We need to wait for the config entry to be reloaded,
        # before restoring the backup.
        # We will do this in the restore nvm progress task,
        # to get a nicer user experience.
        self._async_update_entry(
            {
                "unique_id": str(version_info.home_id),
                CONF_URL: ws_address,
                CONF_USB_PATH: self.usb_path,
                CONF_S0_LEGACY_KEY: self.s0_legacy_key,
                CONF_S2_ACCESS_CONTROL_KEY: self.s2_access_control_key,
                CONF_S2_AUTHENTICATED_KEY: self.s2_authenticated_key,
                CONF_S2_UNAUTHENTICATED_KEY: self.s2_unauthenticated_key,
                CONF_LR_S2_ACCESS_CONTROL_KEY: self.lr_s2_access_control_key,
                CONF_LR_S2_AUTHENTICATED_KEY: self.lr_s2_authenticated_key,
                CONF_USE_ADDON: True,
                CONF_INTEGRATION_CREATED_ADDON: self.integration_created_addon,
            },
            schedule_reload=False,
        )
        return await self.async_step_restore_nvm()

    async def async_step_finish_addon_setup_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Prepare info needed to complete the config entry update.

        Get add-on discovery info and server version info.
        Check for same unique id and abort if not the same unique id.
        """
        config_entry = self._reconfigure_config_entry
        assert config_entry is not None
        if self.revert_reason:
            self.original_addon_config = None
            reason = self.revert_reason
            self.revert_reason = None
            return await self.async_revert_addon_config(reason=reason)

        if not self.ws_address:
            discovery_info = await self._async_get_addon_discovery_info()
            self.ws_address = f"ws://{discovery_info['host']}:{discovery_info['port']}"

        if not self.version_info:
            try:
                self.version_info = await async_get_version_info(
                    self.hass, self.ws_address
                )
            except CannotConnect:
                return await self.async_revert_addon_config(reason="cannot_connect")

        if config_entry.unique_id != str(self.version_info.home_id):
            return await self.async_revert_addon_config(reason="different_device")

        self._async_update_entry(
            {
                CONF_URL: self.ws_address,
                CONF_USB_PATH: self.usb_path,
                CONF_S0_LEGACY_KEY: self.s0_legacy_key,
                CONF_S2_ACCESS_CONTROL_KEY: self.s2_access_control_key,
                CONF_S2_AUTHENTICATED_KEY: self.s2_authenticated_key,
                CONF_S2_UNAUTHENTICATED_KEY: self.s2_unauthenticated_key,
                CONF_LR_S2_ACCESS_CONTROL_KEY: self.lr_s2_access_control_key,
                CONF_LR_S2_AUTHENTICATED_KEY: self.lr_s2_authenticated_key,
                CONF_USE_ADDON: True,
                CONF_INTEGRATION_CREATED_ADDON: self.integration_created_addon,
            }
        )

        return self.async_abort(reason="reconfigure_successful")

    async def async_revert_addon_config(self, reason: str) -> ConfigFlowResult:
        """Abort the options flow.

        If the add-on options have been changed, revert those and restart add-on.
        """
        # If reverting the add-on options failed, abort immediately.
        if self.revert_reason:
            _LOGGER.error(
                "Failed to revert add-on options before aborting flow, reason: %s",
                reason,
            )

        if self.revert_reason or not self.original_addon_config:
            config_entry = self._reconfigure_config_entry
            assert config_entry is not None
            self.hass.config_entries.async_schedule_reload(config_entry.entry_id)
            return self.async_abort(reason=reason)

        self.revert_reason = reason
        addon_config_input = {
            ADDON_USER_INPUT_MAP[addon_key]: addon_val
            for addon_key, addon_val in self.original_addon_config.items()
            if addon_key in ADDON_USER_INPUT_MAP
        }
        _LOGGER.debug("Reverting add-on options, reason: %s", reason)
        return await self.async_step_configure_addon_reconfigure(addon_config_input)

    async def _async_backup_network(self) -> None:
        """Backup the current network."""

        @callback
        def forward_progress(event: dict) -> None:
            """Forward progress events to frontend."""
            self.async_update_progress(event["bytesRead"] / event["total"])

        controller = self._get_driver().controller
        unsub = controller.on("nvm backup progress", forward_progress)
        try:
            self.backup_data = await controller.async_backup_nvm_raw()
        except FailedCommand as err:
            raise AbortFlow(f"Failed to backup network: {err}") from err
        finally:
            unsub()

        # save the backup to a file just in case
        self.backup_filepath = self.hass.config.path(
            f"zwavejs_nvm_backup_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.bin"
        )
        try:
            await self.hass.async_add_executor_job(
                Path(self.backup_filepath).write_bytes,
                self.backup_data,
            )
        except OSError as err:
            raise AbortFlow(f"Failed to save backup file: {err}") from err

    async def _async_restore_network_backup(self) -> None:
        """Restore the backup."""
        assert self.backup_data is not None
        config_entry = self._reconfigure_config_entry
        assert config_entry is not None

        # Reload the config entry to reconnect the client after the addon restart
        await self.hass.config_entries.async_reload(config_entry.entry_id)

        @callback
        def forward_progress(event: dict) -> None:
            """Forward progress events to frontend."""
            if event["event"] == "nvm convert progress":
                # assume convert is 50% of the total progress
                self.async_update_progress(event["bytesRead"] / event["total"] * 0.5)
            elif event["event"] == "nvm restore progress":
                # assume restore is the rest of the progress
                self.async_update_progress(
                    event["bytesWritten"] / event["total"] * 0.5 + 0.5
                )

        controller = self._get_driver().controller
        unsubs = [
            controller.on("nvm convert progress", forward_progress),
            controller.on("nvm restore progress", forward_progress),
        ]
        try:
            await controller.async_restore_nvm(self.backup_data)
        except FailedCommand as err:
            raise AbortFlow(f"Failed to restore network: {err}") from err
        finally:
            for unsub in unsubs:
                unsub()

    def _get_driver(self) -> Driver:
        """Get the driver from the config entry."""
        config_entry = self._reconfigure_config_entry
        assert config_entry is not None
        if config_entry.state != ConfigEntryState.LOADED:
            raise AbortFlow("Configuration entry is not loaded")
        client: Client = config_entry.runtime_data[DATA_CLIENT]
        assert client.driver is not None
        return client.driver


class CannotConnect(HomeAssistantError):
    """Indicate connection error."""


class InvalidInput(HomeAssistantError):
    """Error to indicate input data is invalid."""

    def __init__(self, error: str) -> None:
        """Initialize error."""
        super().__init__()
        self.error = error
