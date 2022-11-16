"""Manage the Silicon Labs Multiprotocol add-on."""
from __future__ import annotations

from abc import abstractmethod
import asyncio
import dataclasses
import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.hassio import (
    AddonError,
    AddonInfo,
    AddonManager,
    AddonState,
    is_hassio,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import (
    AbortFlow,
    FlowHandler,
    FlowManager,
    FlowResult,
)
from homeassistant.helpers.singleton import singleton

from .const import LOGGER, SILABS_MULTIPROTOCOL_ADDON_SLUG

_LOGGER = logging.getLogger(__name__)

DATA_ADDON_MANAGER = "silabs_multiprotocol_addon_manager"

ADDON_SETUP_TIMEOUT = 5
ADDON_SETUP_TIMEOUT_ROUNDS = 40

CONF_ADDON_AUTOFLASH_FW = "autoflash_firmware"
CONF_ADDON_DEVICE = "device"
CONF_ENABLE_MULTI_PAN = "enable_multi_pan"


@singleton(DATA_ADDON_MANAGER)
@callback
def get_addon_manager(hass: HomeAssistant) -> AddonManager:
    """Get the add-on manager."""
    return AddonManager(
        hass,
        LOGGER,
        "Silicon Labs Multiprotocol",
        SILABS_MULTIPROTOCOL_ADDON_SLUG,
    )


@dataclasses.dataclass
class SerialPortSettings:
    """Serial port settings."""

    device: str
    baudrate: str
    flow_control: bool


def get_zigbee_socket(hass, addon_info: AddonInfo) -> str:
    """Return the zigbee socket.

    Raises AddonError on error
    """
    return f"socket://{addon_info.hostname}:9999"


class BaseMultiPanFlow(FlowHandler):
    """Support configuring the Silicon Labs Multiprotocol add-on."""

    def __init__(self) -> None:
        """Set up flow instance."""
        # If we install the add-on we should uninstall it on entry remove.
        self.install_task: asyncio.Task | None = None
        self.start_task: asyncio.Task | None = None

    @property
    @abstractmethod
    def flow_manager(self) -> FlowManager:
        """Return the flow manager of the flow."""

    @abstractmethod
    async def _async_serial_port_settings(self) -> SerialPortSettings:
        """Return the radio serial port settings."""

    async def async_step_install_addon(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Install Silicon Labs Multiprotocol add-on."""
        if not self.install_task:
            self.install_task = self.hass.async_create_task(self._async_install_addon())
            return self.async_show_progress(
                step_id="install_addon", progress_action="install_addon"
            )

        try:
            await self.install_task
        except AddonError as err:
            self.install_task = None
            _LOGGER.error(err)
            return self.async_show_progress_done(next_step_id="install_failed")

        self.install_task = None

        return self.async_show_progress_done(next_step_id="configure_addon")

    async def async_step_install_failed(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Add-on installation failed."""
        return self.async_abort(reason="addon_install_failed")

    async def async_step_start_addon(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Start Silicon Labs Multiprotocol add-on."""
        if not self.start_task:
            self.start_task = self.hass.async_create_task(self._async_start_addon())
            return self.async_show_progress(
                step_id="start_addon", progress_action="start_addon"
            )

        try:
            await self.start_task
        except (AddonError, AbortFlow) as err:
            self.start_task = None
            _LOGGER.error(err)
            return self.async_show_progress_done(next_step_id="start_failed")

        self.start_task = None
        return self.async_show_progress_done(next_step_id="finish_addon_setup")

    async def async_step_start_failed(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Add-on start failed."""
        return self.async_abort(reason="addon_start_failed")

    async def _async_start_addon(self) -> None:
        """Start Silicon Labs Multiprotocol add-on."""
        addon_manager: AddonManager = get_addon_manager(self.hass)
        try:
            await addon_manager.async_schedule_start_addon()
        finally:
            # Continue the flow after show progress when the task is done.
            self.hass.async_create_task(
                self.flow_manager.async_configure(flow_id=self.flow_id)
            )

    @abstractmethod
    async def async_step_configure_addon(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Configure the Silicon Labs Multiprotocol add-on."""

    @abstractmethod
    async def async_step_finish_addon_setup(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Finish setup of the Silicon Labs Multiprotocol add-on."""

    async def _async_get_addon_info(self) -> AddonInfo:
        """Return and cache Silicon Labs Multiprotocol add-on info."""
        addon_manager: AddonManager = get_addon_manager(self.hass)
        try:
            addon_info: AddonInfo = await addon_manager.async_get_addon_info()
        except AddonError as err:
            _LOGGER.error(err)
            raise AbortFlow("addon_info_failed") from err

        return addon_info

    async def _async_set_addon_config(self, config: dict) -> None:
        """Set Silicon Labs Multiprotocol add-on config."""
        addon_manager: AddonManager = get_addon_manager(self.hass)
        try:
            await addon_manager.async_set_addon_options(config)
        except AddonError as err:
            _LOGGER.error(err)
            raise AbortFlow("addon_set_config_failed") from err

    async def _async_install_addon(self) -> None:
        """Install the Silicon Labs Multiprotocol add-on."""
        addon_manager: AddonManager = get_addon_manager(self.hass)
        try:
            await addon_manager.async_schedule_install_addon()
        finally:
            # Continue the flow after show progress when the task is done.
            self.hass.async_create_task(
                self.flow_manager.async_configure(flow_id=self.flow_id)
            )


class OptionsFlowHandler(BaseMultiPanFlow, config_entries.OptionsFlow):
    """Handle an options flow for the Silicon Labs Multiprotocol add-on."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Set up the options flow."""
        super().__init__()
        self.config_entry = config_entry
        self.original_addon_config: dict[str, Any] | None = None
        self.revert_reason: str | None = None

    @property
    def flow_manager(self) -> config_entries.OptionsFlowManager:
        """Return the correct flow manager."""
        return self.hass.config_entries.options

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if not is_hassio(self.hass):
            return self.async_abort(reason="not_hassio")

        return await self.async_step_on_supervisor()

    async def async_step_on_supervisor(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle logic when on Supervisor host."""
        addon_info = await self._async_get_addon_info()

        if addon_info.state == AddonState.NOT_INSTALLED:
            return await self.async_step_addon_not_installed()
        return await self.async_step_addon_installed()

    async def async_step_addon_not_installed(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle logic when the addon is not yet installed."""
        if user_input is None:
            return self.async_show_form(
                step_id="addon_not_installed",
                data_schema=vol.Schema(
                    {vol.Required(CONF_ENABLE_MULTI_PAN, default=False): bool}
                ),
            )
        if not user_input[CONF_ENABLE_MULTI_PAN]:
            return self.async_create_entry(title="", data={})

        return await self.async_step_install_addon()

    async def async_step_configure_addon(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Configure the Silicon Labs Multiprotocol add-on."""
        addon_info = await self._async_get_addon_info()

        addon_config = addon_info.options

        serial_port_settings = await self._async_serial_port_settings()
        new_addon_config = {
            **addon_config,
            CONF_ADDON_AUTOFLASH_FW: True,
            **dataclasses.asdict(serial_port_settings),
        }

        if new_addon_config != addon_config:
            # Copy the add-on config to keep the objects separate.
            self.original_addon_config = dict(addon_config)
            _LOGGER.debug("Reconfiguring addon with %s", new_addon_config)
            await self._async_set_addon_config(new_addon_config)

        return await self.async_step_start_addon()

    async def async_step_finish_addon_setup(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Prepare info needed to complete the config entry update."""
        # Always reload entry after installing the addon.
        self.hass.async_create_task(
            self.hass.config_entries.async_reload(self.config_entry.entry_id)
        )

        return self.async_create_entry(title="", data={})

    async def async_step_addon_installed(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle logic when the addon is already installed."""
        addon_info = await self._async_get_addon_info()

        serial_device = (await self._async_serial_port_settings()).device
        if addon_info.options.get(CONF_ADDON_DEVICE) == serial_device:
            return await self.async_step_show_revert_guide()
        return await self.async_step_addon_installed_other_device()

    async def async_step_show_revert_guide(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Link to a guide for reverting to Zigbee firmware."""
        if user_input is None:
            return self.async_show_form(step_id="show_revert_guide")
        return self.async_create_entry(title="", data={})

    async def async_step_addon_installed_other_device(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Show dialog explaining the addon is in use by another device."""
        if user_input is None:
            return self.async_show_form(step_id="addon_installed_other_device")
        return self.async_create_entry(title="", data={})
