"""Manage the Silicon Labs Multiprotocol add-on."""
from __future__ import annotations

from abc import ABC, abstractmethod
import asyncio
import dataclasses
import logging
from typing import Any

import voluptuous as vol
import yarl

from homeassistant import config_entries
from homeassistant.components.hassio import (
    AddonError,
    AddonInfo,
    AddonManager,
    AddonState,
    hostname_from_addon_slug,
    is_hassio,
)
from homeassistant.components.zha import DOMAIN as ZHA_DOMAIN
from homeassistant.components.zha.radio_manager import ZhaMultiPANMigrationHelper
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import AbortFlow, FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.singleton import singleton

from .const import LOGGER, SILABS_FLASHER_ADDON_SLUG, SILABS_MULTIPROTOCOL_ADDON_SLUG

_LOGGER = logging.getLogger(__name__)

DATA_MULTIPROTOCOL_ADDON_MANAGER = "silabs_multiprotocol_addon_manager"
DATA_FLASHER_ADDON_MANAGER = "silabs_flasher"

ADDON_STATE_POLL_INTERVAL = 3

CONF_ADDON_AUTOFLASH_FW = "autoflash_firmware"
CONF_ADDON_DEVICE = "device"
CONF_ENABLE_MULTI_PAN = "enable_multi_pan"


@singleton(DATA_MULTIPROTOCOL_ADDON_MANAGER)
@callback
def get_multiprotocol_addon_manager(hass: HomeAssistant) -> AddonManager:
    """Get the multiprotocol add-on manager."""
    return AddonManager(
        hass,
        LOGGER,
        "Silicon Labs Multiprotocol",
        SILABS_MULTIPROTOCOL_ADDON_SLUG,
    )


@singleton(DATA_FLASHER_ADDON_MANAGER)
@callback
def get_flasher_addon_manager(hass: HomeAssistant) -> AddonManager:
    """Get the flasher add-on manager."""
    return AddonManager(
        hass,
        LOGGER,
        "Silicon Labs Flasher",
        SILABS_FLASHER_ADDON_SLUG,
    )


@dataclasses.dataclass
class SerialPortSettings:
    """Serial port settings."""

    device: str
    baudrate: str
    flow_control: bool


def get_zigbee_socket() -> str:
    """Return the zigbee socket.

    Raises AddonError on error
    """
    hostname = hostname_from_addon_slug(SILABS_MULTIPROTOCOL_ADDON_SLUG)
    return f"socket://{hostname}:9999"


def is_multiprotocol_url(url: str) -> bool:
    """Return if the URL points at the Multiprotocol add-on."""
    parsed = yarl.URL(url)
    hostname = hostname_from_addon_slug(SILABS_MULTIPROTOCOL_ADDON_SLUG)
    return parsed.host == hostname


class OptionsFlowHandler(config_entries.OptionsFlow, ABC):
    """Handle an options flow for the Silicon Labs Multiprotocol add-on."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Set up the options flow."""
        # If we install the add-on we should uninstall it on entry remove.
        self.install_task: asyncio.Task | None = None
        self.start_task: asyncio.Task | None = None
        self.stop_task: asyncio.Task | None = None
        self._zha_migration_mgr: ZhaMultiPANMigrationHelper | None = None
        self.config_entry = config_entry
        self.original_addon_config: dict[str, Any] | None = None
        self.revert_reason: str | None = None

    @abstractmethod
    async def _async_serial_port_settings(self) -> SerialPortSettings:
        """Return the radio serial port settings."""

    @abstractmethod
    async def _async_zha_physical_discovery(self) -> dict[str, Any]:
        """Return ZHA discovery data when multiprotocol FW is not used.

        Passed to ZHA do determine if the ZHA config entry is connected to the radio
        being migrated.
        """

    @abstractmethod
    def _hardware_name(self) -> str:
        """Return the name of the hardware."""

    @abstractmethod
    def _zha_name(self) -> str:
        """Return the ZHA name."""

    @property
    def flow_manager(self) -> config_entries.OptionsFlowManager:
        """Return the correct flow manager."""
        return self.hass.config_entries.options

    async def _async_get_addon_info(self, addon_manager: AddonManager) -> AddonInfo:
        """Return and cache Silicon Labs Multiprotocol add-on info."""
        try:
            addon_info: AddonInfo = await addon_manager.async_get_addon_info()
        except AddonError as err:
            _LOGGER.error(err)
            raise AbortFlow(
                "addon_info_failed",
                description_placeholders={"addon_name": "Silicon Labs Multiprotocol"},
            ) from err

        return addon_info

    async def _async_set_addon_config(
        self, config: dict, addon_manager: AddonManager
    ) -> None:
        """Set Silicon Labs Multiprotocol add-on config."""
        try:
            await addon_manager.async_set_addon_options(config)
        except AddonError as err:
            _LOGGER.error(err)
            raise AbortFlow("addon_set_config_failed") from err

    async def _async_install_addon(self, addon_manager: AddonManager) -> None:
        """Install an add-on."""
        try:
            await addon_manager.async_schedule_install_addon()
        finally:
            # Continue the flow after show progress when the task is done.
            self.hass.async_create_task(
                self.flow_manager.async_configure(flow_id=self.flow_id)
            )

    async def _async_uninstall_addon(self, addon_manager: AddonManager) -> None:
        """Uninstall an add-on."""
        try:
            await addon_manager.async_uninstall_addon()
            await self._async_wait_until_addon_state(
                addon_manager, AddonState.NOT_INSTALLED
            )
        finally:
            # Continue the flow after show progress when the task is done.
            self.hass.async_create_task(
                self.flow_manager.async_configure(flow_id=self.flow_id)
            )

    async def _async_start_addon(
        self, addon_manager: AddonManager, wait_until_done: bool = False
    ) -> None:
        """Start an add-on."""
        try:
            await addon_manager.async_schedule_start_addon()
            await self._async_wait_until_addon_state(addon_manager, AddonState.RUNNING)

            if wait_until_done:
                await self._async_wait_until_addon_state(
                    addon_manager, AddonState.NOT_RUNNING
                )
        finally:
            # Continue the flow after show progress when the task is done.
            self.hass.async_create_task(
                self.flow_manager.async_configure(flow_id=self.flow_id)
            )

    async def _async_wait_until_addon_state(
        self, addon_manager: AddonManager, state: AddonState
    ) -> None:
        """Poll an addon's info until it is in a specific state."""
        while True:
            try:
                info = await addon_manager.async_get_addon_info()
            except AddonError:
                info = None

            _LOGGER.debug("Waiting for addon to be in state %s: %s", state, info)

            if info is not None and info.state == state:
                break

            await asyncio.sleep(ADDON_STATE_POLL_INTERVAL)

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
        addon_manager: AddonManager = get_multiprotocol_addon_manager(self.hass)
        addon_info = await self._async_get_addon_info(addon_manager)

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
                description_placeholders={"hardware_name": self._hardware_name()},
            )
        if not user_input[CONF_ENABLE_MULTI_PAN]:
            return self.async_create_entry(title="", data={})

        return await self.async_step_install_addon()

    async def async_step_install_addon(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Install Silicon Labs Multiprotocol add-on."""
        if not self.install_task:
            addon_manager: AddonManager = get_multiprotocol_addon_manager(self.hass)
            self.install_task = self.hass.async_create_task(
                self._async_install_addon(addon_manager)
            )
            return self.async_show_progress(
                step_id="install_addon",
                progress_action="install_addon",
                description_placeholders={"addon_name": "Silicon Labs Multiprotocol"},
            )

        try:
            await self.install_task
        except AddonError as err:
            self.install_task = None
            _LOGGER.error(err)
            return self.async_show_progress_done(next_step_id="install_failed")
        finally:
            self.install_task = None

        return self.async_show_progress_done(next_step_id="configure_addon")

    async def async_step_install_failed(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Add-on installation failed."""
        return self.async_abort(
            reason="addon_install_failed",
            description_placeholders={"addon_name": "Silicon Labs Multiprotocol"},
        )

    async def async_step_configure_addon(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Configure the Silicon Labs Multiprotocol add-on."""
        addon_manager: AddonManager = get_multiprotocol_addon_manager(self.hass)
        addon_info = await self._async_get_addon_info(addon_manager)

        addon_config = addon_info.options

        serial_port_settings = await self._async_serial_port_settings()
        new_addon_config = {
            **addon_config,
            CONF_ADDON_AUTOFLASH_FW: True,
            **dataclasses.asdict(serial_port_settings),
        }

        # Initiate ZHA migration
        zha_entries = self.hass.config_entries.async_entries(ZHA_DOMAIN)

        if zha_entries:
            zha_migration_mgr = ZhaMultiPANMigrationHelper(self.hass, zha_entries[0])
            migration_data = {
                "new_discovery_info": {
                    "name": self._zha_name(),
                    "port": {
                        "path": get_zigbee_socket(),
                    },
                    "radio_type": "ezsp",
                },
                "old_discovery_info": await self._async_zha_physical_discovery(),
            }
            _LOGGER.debug("Starting ZHA migration with: %s", migration_data)
            try:
                if await zha_migration_mgr.async_initiate_migration(migration_data):
                    self._zha_migration_mgr = zha_migration_mgr
            except Exception as err:
                _LOGGER.exception("Unexpected exception during ZHA migration")
                raise AbortFlow("zha_migration_failed") from err

        if new_addon_config != addon_config:
            # Copy the add-on config to keep the objects separate.
            self.original_addon_config = dict(addon_config)
            _LOGGER.debug("Reconfiguring addon with %s", new_addon_config)
            await self._async_set_addon_config(new_addon_config, addon_manager)

        return await self.async_step_start_addon()

    async def async_step_start_addon(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Start Silicon Labs Multiprotocol add-on."""
        if not self.start_task:
            addon_manager: AddonManager = get_multiprotocol_addon_manager(self.hass)
            self.start_task = self.hass.async_create_task(
                self._async_start_addon(addon_manager)
            )
            return self.async_show_progress(
                step_id="start_addon",
                progress_action="start_addon",
                description_placeholders={"addon_name": "Silicon Labs Multiprotocol"},
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
        return self.async_abort(
            reason="addon_start_failed",
            description_placeholders={"addon_name": "Silicon Labs Multiprotocol"},
        )

    async def async_step_finish_addon_setup(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Prepare info needed to complete the config entry update."""
        # Always reload entry after installing the addon.
        self.hass.async_create_task(
            self.hass.config_entries.async_reload(self.config_entry.entry_id)
        )

        # Finish ZHA migration if needed
        if self._zha_migration_mgr:
            try:
                await self._zha_migration_mgr.async_finish_migration()
            except Exception as err:
                _LOGGER.exception("Unexpected exception during ZHA migration")
                raise AbortFlow("zha_migration_failed") from err

        return self.async_create_entry(title="", data={})

    async def async_step_addon_installed_other_device(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Show dialog explaining the addon is in use by another device."""
        if user_input is None:
            return self.async_show_form(step_id="addon_installed_other_device")
        return self.async_create_entry(title="", data={})

    async def async_step_addon_installed(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle logic when the addon is already installed."""
        addon_manager: AddonManager = get_multiprotocol_addon_manager(self.hass)
        addon_info = await self._async_get_addon_info(addon_manager)

        serial_device = (await self._async_serial_port_settings()).device
        if addon_info.options.get(CONF_ADDON_DEVICE) != serial_device:
            return await self.async_step_addon_installed_other_device()
        return await self.async_step_firmware_revert()

    async def async_step_firmware_revert(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Show progress dialog for installing flasher addon."""
        addon_manager: AddonManager = get_flasher_addon_manager(self.hass)
        addon_info = await self._async_get_addon_info(addon_manager)

        _LOGGER.debug("Flasher addon state: %s", addon_info)

        if addon_info.state == AddonState.NOT_INSTALLED:
            if not self.install_task:
                self.install_task = self.hass.async_create_task(
                    self._async_install_addon(addon_manager)
                )
                return self.async_show_progress(
                    step_id="firmware_revert",
                    progress_action="install_addon",
                    description_placeholders={"addon_name": "Silicon Labs Flasher"},
                )

            try:
                await self.install_task
            except AddonError as err:
                _LOGGER.error(err)
                return self.async_show_progress_done(next_step_id="install_failed")
            finally:
                self.install_task = None

        return self.async_show_progress_done(next_step_id="configure_flasher_addon")

    async def async_step_configure_flasher_addon(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Perform initial backup and reconfigure ZHA."""
        zha_entries = self.hass.config_entries.async_entries(ZHA_DOMAIN)
        new_settings = await self._async_serial_port_settings()

        _LOGGER.debug("Using new ZHA settings: %s", new_settings)

        if zha_entries:
            zha_migration_mgr = ZhaMultiPANMigrationHelper(self.hass, zha_entries[0])
            migration_data = {
                "new_discovery_info": {
                    "name": self._hardware_name(),
                    "port": {
                        "path": new_settings.device,
                        "baudrate": int(new_settings.baudrate),
                        "flow_control": (
                            "hardware" if new_settings.flow_control else None
                        ),
                    },
                    "radio_type": "ezsp",
                },
                "old_discovery_info": {
                    "hw": {
                        "name": self._zha_name(),
                        "port": {"path": get_zigbee_socket()},
                        "radio_type": "ezsp",
                    }
                },
            }
            _LOGGER.debug("Starting ZHA migration with: %s", migration_data)
            try:
                if await zha_migration_mgr.async_initiate_migration(migration_data):
                    self._zha_migration_mgr = zha_migration_mgr
            except Exception as err:
                _LOGGER.exception("Unexpected exception during ZHA migration")
                raise AbortFlow("zha_migration_failed") from err

        addon_manager: AddonManager = get_flasher_addon_manager(self.hass)
        addon_info = await self._async_get_addon_info(addon_manager)
        new_addon_config = {
            **addon_info.options,
            "device": new_settings.device,
            "flow_control": new_settings.flow_control,
        }

        _LOGGER.debug("Reconfiguring addon with %s", new_addon_config)
        await self._async_set_addon_config(new_addon_config, addon_manager)

        return await self.async_step_uninstall_multiprotocol_addon()

    async def async_step_uninstall_multiprotocol_addon(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Uninstall Silicon Labs Multiprotocol add-on."""

        if not self.stop_task:
            addon_manager: AddonManager = get_multiprotocol_addon_manager(self.hass)
            self.stop_task = self.hass.async_create_task(
                self._async_uninstall_addon(addon_manager)
            )
            return self.async_show_progress(
                step_id="uninstall_multiprotocol_addon",
                progress_action="uninstall_multiprotocol_addon",
                description_placeholders={"addon_name": "Silicon Labs Multiprotocol"},
            )

        try:
            await self.stop_task
        finally:
            self.stop_task = None

        return self.async_show_progress_done(next_step_id="start_flasher_addon")

    async def async_step_start_flasher_addon(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Start Silicon Labs Flasher add-on."""

        if not self.start_task:
            addon_manager: AddonManager = get_flasher_addon_manager(self.hass)
            self.start_task = self.hass.async_create_task(
                self._async_start_addon(addon_manager, wait_until_done=True)
            )
            return self.async_show_progress(
                step_id="start_flasher_addon",
                progress_action="start_flasher_addon",
                description_placeholders={"addon_name": "Silicon Labs Flasher"},
            )

        try:
            await self.start_task
        except (AddonError, AbortFlow) as err:
            _LOGGER.error(err)
            return self.async_show_progress_done(next_step_id="flasher_failed")
        finally:
            self.start_task = None

        return self.async_show_progress_done(next_step_id="flashing_complete")

    async def async_step_flasher_failed(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Flasher add-on start failed."""
        return self.async_abort(
            reason="addon_start_failed",
            description_placeholders={"addon_name": "Silicon Labs Flasher"},
        )

    async def async_step_flashing_complete(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Finish flashing and update the config entry."""
        flasher_addon_manager: AddonManager = get_flasher_addon_manager(self.hass)
        await self._async_uninstall_addon(flasher_addon_manager)

        # Always reload entry after installing the addon.
        self.hass.async_create_task(
            self.hass.config_entries.async_reload(self.config_entry.entry_id)
        )

        # Finish ZHA migration if needed
        if self._zha_migration_mgr:
            try:
                await self._zha_migration_mgr.async_finish_migration()
            except Exception as err:
                _LOGGER.exception("Unexpected exception during ZHA migration")
                raise AbortFlow("zha_migration_failed") from err

        return self.async_create_entry(title="", data={})


async def check_multi_pan_addon(hass: HomeAssistant) -> None:
    """Check the multi-PAN addon state, and start it if installed but not started.

    Does nothing if Hass.io is not loaded.
    Raises on error or if the add-on is installed but not started.
    """
    if not is_hassio(hass):
        return

    addon_manager: AddonManager = get_multiprotocol_addon_manager(hass)
    try:
        addon_info: AddonInfo = await addon_manager.async_get_addon_info()
    except AddonError as err:
        _LOGGER.error(err)
        raise HomeAssistantError from err

    # Request the addon to start if it's not started
    # addon_manager.async_start_addon returns as soon as the start request has been sent
    # and does not wait for the addon to be started, so we raise below
    if addon_info.state == AddonState.NOT_RUNNING:
        await addon_manager.async_start_addon()

    if addon_info.state not in (AddonState.NOT_INSTALLED, AddonState.RUNNING):
        _LOGGER.debug("Multi pan addon installed and in state %s", addon_info.state)
        raise HomeAssistantError


async def multi_pan_addon_using_device(hass: HomeAssistant, device_path: str) -> bool:
    """Return True if the multi-PAN addon is using the given device.

    Returns False if Hass.io is not loaded, the addon is not running or the addon is
    connected to another device.
    """
    if not is_hassio(hass):
        return False

    addon_manager: AddonManager = get_multiprotocol_addon_manager(hass)
    addon_info: AddonInfo = await addon_manager.async_get_addon_info()

    if addon_info.state != AddonState.RUNNING:
        return False

    if addon_info.options["device"] != device_path:
        return False

    return True
