"""Manage the Silicon Labs Multiprotocol add-on."""
from __future__ import annotations

from abc import ABC, abstractmethod
import asyncio
from collections.abc import Awaitable
import dataclasses
import logging
from typing import Any, Protocol

import async_timeout
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
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import AbortFlow, FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.integration_platform import (
    async_process_integration_platforms,
)
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)
from homeassistant.helpers.singleton import singleton
from homeassistant.helpers.storage import Store

from .const import LOGGER, SILABS_FLASHER_ADDON_SLUG, SILABS_MULTIPROTOCOL_ADDON_SLUG

_LOGGER = logging.getLogger(__name__)

DATA_MULTIPROTOCOL_ADDON_MANAGER = "silabs_multiprotocol_addon_manager"
DATA_FLASHER_ADDON_MANAGER = "silabs_flasher"

ADDON_STATE_POLL_INTERVAL = 3
ADDON_INFO_POLL_TIMEOUT = 15 * 60

CONF_ADDON_AUTOFLASH_FW = "autoflash_firmware"
CONF_ADDON_DEVICE = "device"
CONF_DISABLE_MULTI_PAN = "disable_multi_pan"
CONF_ENABLE_MULTI_PAN = "enable_multi_pan"

DEFAULT_CHANNEL = 15
DEFAULT_CHANNEL_CHANGE_DELAY = 5 * 60  # Thread recommendation

STORAGE_KEY = "homeassistant_hardware.silabs"
STORAGE_VERSION_MAJOR = 1
STORAGE_VERSION_MINOR = 1
SAVE_DELAY = 10


@singleton(DATA_MULTIPROTOCOL_ADDON_MANAGER)
async def get_multiprotocol_addon_manager(
    hass: HomeAssistant,
) -> MultiprotocolAddonManager:
    """Get the add-on manager."""
    manager = MultiprotocolAddonManager(hass)
    await manager.async_setup()
    return manager


class WaitingAddonManager(AddonManager):
    """Addon manager which supports waiting operations for managing an addon."""

    async def async_wait_until_addon_state(self, *states: AddonState) -> None:
        """Poll an addon's info until it is in a specific state."""
        async with async_timeout.timeout(ADDON_INFO_POLL_TIMEOUT):
            while True:
                try:
                    info = await self.async_get_addon_info()
                except AddonError:
                    info = None

                _LOGGER.debug("Waiting for addon to be in state %s: %s", states, info)

                if info is not None and info.state in states:
                    break

                await asyncio.sleep(ADDON_STATE_POLL_INTERVAL)

    async def async_start_addon_waiting(self) -> None:
        """Start an add-on."""
        await self.async_schedule_start_addon()
        await self.async_wait_until_addon_state(AddonState.RUNNING)

    async def async_install_addon_waiting(self) -> None:
        """Install an add-on."""
        await self.async_schedule_install_addon()
        await self.async_wait_until_addon_state(
            AddonState.RUNNING,
            AddonState.NOT_RUNNING,
        )

    async def async_uninstall_addon_waiting(self) -> None:
        """Uninstall an add-on."""
        try:
            info = await self.async_get_addon_info()
        except AddonError:
            info = None

        # Do not try to uninstall an addon if it is already uninstalled
        if info is not None and info.state == AddonState.NOT_INSTALLED:
            return

        await self.async_uninstall_addon()
        await self.async_wait_until_addon_state(AddonState.NOT_INSTALLED)


class MultiprotocolAddonManager(WaitingAddonManager):
    """Silicon Labs Multiprotocol add-on manager."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the manager."""
        super().__init__(
            hass,
            LOGGER,
            "Silicon Labs Multiprotocol",
            SILABS_MULTIPROTOCOL_ADDON_SLUG,
        )
        self._channel: int | None = None
        self._platforms: dict[str, MultipanProtocol] = {}
        self._store: Store[dict[str, Any]] = Store(
            hass,
            STORAGE_VERSION_MAJOR,
            STORAGE_KEY,
            atomic_writes=True,
            minor_version=STORAGE_VERSION_MINOR,
        )

    async def async_setup(self) -> None:
        """Set up the manager."""
        await async_process_integration_platforms(
            self._hass, "silabs_multiprotocol", self._register_multipan_platform
        )
        await self.async_load()

    async def _register_multipan_platform(
        self, hass: HomeAssistant, integration_domain: str, platform: MultipanProtocol
    ) -> None:
        """Register a multipan platform."""
        self._platforms[integration_domain] = platform

        channel = await platform.async_get_channel(hass)
        using_multipan = await platform.async_using_multipan(hass)

        _LOGGER.info(
            "Registering new multipan platform '%s', using multipan: %s, channel: %s",
            integration_domain,
            using_multipan,
            channel,
        )

        if self._channel is not None or not using_multipan:
            return

        if channel is None:
            return

        _LOGGER.info(
            "Setting multipan channel to %s (source: '%s')",
            channel,
            integration_domain,
        )
        self.async_set_channel(channel)

    async def async_change_channel(
        self, channel: int, delay: float
    ) -> list[asyncio.Task]:
        """Change the channel and notify platforms."""
        self.async_set_channel(channel)

        tasks = []

        for platform in self._platforms.values():
            if not await platform.async_using_multipan(self._hass):
                continue
            task = await platform.async_change_channel(self._hass, channel, delay)
            if not task:
                continue
            tasks.append(task)

        return tasks

    async def async_active_platforms(self) -> list[str]:
        """Return a list of platforms using the multipan radio."""
        active_platforms: list[str] = []

        for integration_domain, platform in self._platforms.items():
            if not await platform.async_using_multipan(self._hass):
                continue
            active_platforms.append(integration_domain)

        return active_platforms

    @callback
    def async_get_channel(self) -> int | None:
        """Get the channel."""
        return self._channel

    @callback
    def async_set_channel(self, channel: int) -> None:
        """Set the channel without notifying platforms.

        This must only be called when first initializing the manager.
        """
        self._channel = channel
        self.async_schedule_save()

    async def async_load(self) -> None:
        """Load the store."""
        data = await self._store.async_load()

        if data is not None:
            self._channel = data["channel"]

    @callback
    def async_schedule_save(self) -> None:
        """Schedule saving the store."""
        self._store.async_delay_save(self._data_to_save, SAVE_DELAY)

    @callback
    def _data_to_save(self) -> dict[str, list[dict[str, str | None]]]:
        """Return data to store in a file."""
        data: dict[str, Any] = {}
        data["channel"] = self._channel
        return data


class MultipanProtocol(Protocol):
    """Define the format of multipan platforms."""

    async def async_change_channel(
        self, hass: HomeAssistant, channel: int, delay: float
    ) -> asyncio.Task | None:
        """Set the channel to be used.

        Does nothing if not configured or the multiprotocol add-on is not used.
        """

    async def async_get_channel(self, hass: HomeAssistant) -> int | None:
        """Return the channel.

        Returns None if not configured or the multiprotocol add-on is not used.
        """

    async def async_using_multipan(self, hass: HomeAssistant) -> bool:
        """Return if the multiprotocol device is used.

        Returns False if not configured.
        """


@singleton(DATA_FLASHER_ADDON_MANAGER)
@callback
def get_flasher_addon_manager(hass: HomeAssistant) -> WaitingAddonManager:
    """Get the flasher add-on manager."""
    return WaitingAddonManager(
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
        # pylint: disable-next=import-outside-toplevel
        from homeassistant.components.zha.radio_manager import (
            ZhaMultiPANMigrationHelper,
        )

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

    async def _resume_flow_when_done(self, awaitable: Awaitable) -> None:
        try:
            await awaitable
        finally:
            self.hass.async_create_task(
                self.flow_manager.async_configure(flow_id=self.flow_id)
            )

    async def _async_get_addon_info(self, addon_manager: AddonManager) -> AddonInfo:
        """Return and cache Silicon Labs Multiprotocol add-on info."""
        try:
            addon_info: AddonInfo = await addon_manager.async_get_addon_info()
        except AddonError as err:
            _LOGGER.error(err)
            raise AbortFlow(
                "addon_info_failed",
                description_placeholders={"addon_name": addon_manager.addon_name},
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
        multipan_manager = await get_multiprotocol_addon_manager(self.hass)
        addon_info = await self._async_get_addon_info(multipan_manager)

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
            multipan_manager = await get_multiprotocol_addon_manager(self.hass)
            self.install_task = self.hass.async_create_task(
                self._resume_flow_when_done(
                    multipan_manager.async_install_addon_waiting()
                ),
                "SiLabs Multiprotocol addon install",
            )
            return self.async_show_progress(
                step_id="install_addon",
                progress_action="install_addon",
                description_placeholders={"addon_name": multipan_manager.addon_name},
            )

        try:
            await self.install_task
        except AddonError as err:
            _LOGGER.error(err)
            return self.async_show_progress_done(next_step_id="install_failed")
        finally:
            self.install_task = None

        return self.async_show_progress_done(next_step_id="configure_addon")

    async def async_step_install_failed(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Add-on installation failed."""
        multipan_manager = await get_multiprotocol_addon_manager(self.hass)
        return self.async_abort(
            reason="addon_install_failed",
            description_placeholders={"addon_name": multipan_manager.addon_name},
        )

    async def async_step_configure_addon(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Configure the Silicon Labs Multiprotocol add-on."""
        # pylint: disable-next=import-outside-toplevel
        from homeassistant.components.zha import DOMAIN as ZHA_DOMAIN

        # pylint: disable-next=import-outside-toplevel
        from homeassistant.components.zha.radio_manager import (
            ZhaMultiPANMigrationHelper,
        )

        # pylint: disable-next=import-outside-toplevel
        from homeassistant.components.zha.silabs_multiprotocol import (
            async_get_channel as async_get_zha_channel,
        )

        multipan_manager = await get_multiprotocol_addon_manager(self.hass)
        addon_info = await self._async_get_addon_info(multipan_manager)

        addon_config = addon_info.options

        serial_port_settings = await self._async_serial_port_settings()
        new_addon_config = {
            **addon_config,
            CONF_ADDON_AUTOFLASH_FW: True,
            **dataclasses.asdict(serial_port_settings),
        }

        multipan_channel = DEFAULT_CHANNEL

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

            if (zha_channel := await async_get_zha_channel(self.hass)) is not None:
                multipan_channel = zha_channel

        # Initialize the shared channel
        multipan_manager = await get_multiprotocol_addon_manager(self.hass)
        multipan_manager.async_set_channel(multipan_channel)

        if new_addon_config != addon_config:
            # Copy the add-on config to keep the objects separate.
            self.original_addon_config = dict(addon_config)
            _LOGGER.debug("Reconfiguring addon with %s", new_addon_config)
            await self._async_set_addon_config(new_addon_config, multipan_manager)

        return await self.async_step_start_addon()

    async def async_step_start_addon(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Start Silicon Labs Multiprotocol add-on."""
        if not self.start_task:
            multipan_manager = await get_multiprotocol_addon_manager(self.hass)
            self.start_task = self.hass.async_create_task(
                self._resume_flow_when_done(
                    multipan_manager.async_start_addon_waiting()
                )
            )
            return self.async_show_progress(
                step_id="start_addon",
                progress_action="start_addon",
                description_placeholders={"addon_name": multipan_manager.addon_name},
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
        multipan_manager = await get_multiprotocol_addon_manager(self.hass)
        return self.async_abort(
            reason="addon_start_failed",
            description_placeholders={"addon_name": multipan_manager.addon_name},
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
        multipan_manager = await get_multiprotocol_addon_manager(self.hass)
        addon_info = await self._async_get_addon_info(multipan_manager)

        serial_device = (await self._async_serial_port_settings()).device
        if addon_info.options.get(CONF_ADDON_DEVICE) != serial_device:
            return await self.async_step_addon_installed_other_device()
        return await self.async_step_show_addon_menu()

    async def async_step_show_addon_menu(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Show menu options for the addon."""
        return self.async_show_menu(
            step_id="addon_menu",
            menu_options=[
                "reconfigure_addon",
                "uninstall_addon",
            ],
        )

    async def async_step_reconfigure_addon(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Reconfigure the addon."""
        multipan_manager = await get_multiprotocol_addon_manager(self.hass)
        active_platforms = await multipan_manager.async_active_platforms()
        if set(active_platforms) != {"otbr", "zha"}:
            return await self.async_step_notify_unknown_multipan_user()
        return await self.async_step_change_channel()

    async def async_step_notify_unknown_multipan_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Notify that there may be unknown multipan platforms."""
        if user_input is None:
            return self.async_show_form(
                step_id="notify_unknown_multipan_user",
            )
        return await self.async_step_change_channel()

    async def async_step_change_channel(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Change the channel."""
        multipan_manager = await get_multiprotocol_addon_manager(self.hass)
        if user_input is None:
            channels = [str(x) for x in range(11, 27)]
            suggested_channel = DEFAULT_CHANNEL
            if (channel := multipan_manager.async_get_channel()) is not None:
                suggested_channel = channel
            data_schema = vol.Schema(
                {
                    vol.Required(
                        "channel",
                        description={"suggested_value": str(suggested_channel)},
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=channels, mode=SelectSelectorMode.DROPDOWN
                        )
                    )
                }
            )
            return self.async_show_form(
                step_id="change_channel", data_schema=data_schema
            )

        # Change the shared channel
        await multipan_manager.async_change_channel(
            int(user_input["channel"]), DEFAULT_CHANNEL_CHANGE_DELAY
        )
        return await self.async_step_notify_channel_change()

    async def async_step_notify_channel_change(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Notify that the channel change will take about five minutes."""
        if user_input is None:
            return self.async_show_form(
                step_id="notify_channel_change",
                description_placeholders={
                    "delay_minutes": str(DEFAULT_CHANNEL_CHANGE_DELAY // 60)
                },
            )
        return self.async_create_entry(title="", data={})

    async def async_step_uninstall_addon(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Uninstall the addon and revert the firmware."""
        if user_input is None:
            return self.async_show_form(
                step_id="uninstall_addon",
                data_schema=vol.Schema(
                    {vol.Required(CONF_DISABLE_MULTI_PAN, default=False): bool}
                ),
                description_placeholders={"hardware_name": self._hardware_name()},
            )
        if not user_input[CONF_DISABLE_MULTI_PAN]:
            return self.async_create_entry(title="", data={})

        return await self.async_step_firmware_revert()

    async def async_step_firmware_revert(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Install the flasher addon, if necessary."""

        flasher_manager = get_flasher_addon_manager(self.hass)
        addon_info = await self._async_get_addon_info(flasher_manager)

        if addon_info.state == AddonState.NOT_INSTALLED:
            return await self.async_step_install_flasher_addon()

        if addon_info.state == AddonState.NOT_RUNNING:
            return await self.async_step_configure_flasher_addon()

        # If the addon is already installed and running, fail
        return self.async_abort(
            reason="addon_already_running",
            description_placeholders={"addon_name": flasher_manager.addon_name},
        )

    async def async_step_install_flasher_addon(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Show progress dialog for installing flasher addon."""
        flasher_manager = get_flasher_addon_manager(self.hass)
        addon_info = await self._async_get_addon_info(flasher_manager)

        _LOGGER.debug("Flasher addon state: %s", addon_info)

        if not self.install_task:
            self.install_task = self.hass.async_create_task(
                self._resume_flow_when_done(
                    flasher_manager.async_install_addon_waiting()
                ),
                "SiLabs Flasher addon install",
            )
            return self.async_show_progress(
                step_id="install_flasher_addon",
                progress_action="install_addon",
                description_placeholders={"addon_name": flasher_manager.addon_name},
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
        # pylint: disable-next=import-outside-toplevel
        from homeassistant.components.zha import DOMAIN as ZHA_DOMAIN

        # pylint: disable-next=import-outside-toplevel
        from homeassistant.components.zha.radio_manager import (
            ZhaMultiPANMigrationHelper,
        )

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

        flasher_manager = get_flasher_addon_manager(self.hass)
        addon_info = await self._async_get_addon_info(flasher_manager)
        new_addon_config = {
            **addon_info.options,
            "device": new_settings.device,
            "flow_control": new_settings.flow_control,
        }

        _LOGGER.debug("Reconfiguring flasher addon with %s", new_addon_config)
        await self._async_set_addon_config(new_addon_config, flasher_manager)

        return await self.async_step_uninstall_multiprotocol_addon()

    async def async_step_uninstall_multiprotocol_addon(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Uninstall Silicon Labs Multiprotocol add-on."""

        if not self.stop_task:
            multipan_manager = await get_multiprotocol_addon_manager(self.hass)
            self.stop_task = self.hass.async_create_task(
                self._resume_flow_when_done(
                    multipan_manager.async_uninstall_addon_waiting()
                ),
                "SiLabs Multiprotocol addon uninstall",
            )
            return self.async_show_progress(
                step_id="uninstall_multiprotocol_addon",
                progress_action="uninstall_multiprotocol_addon",
                description_placeholders={"addon_name": multipan_manager.addon_name},
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
            flasher_manager = get_flasher_addon_manager(self.hass)

            async def start_and_wait_until_done() -> None:
                await flasher_manager.async_start_addon_waiting()
                # Now that the addon is running, wait for it to finish
                await flasher_manager.async_wait_until_addon_state(
                    AddonState.NOT_RUNNING
                )

            self.start_task = self.hass.async_create_task(
                self._resume_flow_when_done(start_and_wait_until_done())
            )
            return self.async_show_progress(
                step_id="start_flasher_addon",
                progress_action="start_flasher_addon",
                description_placeholders={"addon_name": flasher_manager.addon_name},
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
        flasher_manager = get_flasher_addon_manager(self.hass)
        return self.async_abort(
            reason="addon_start_failed",
            description_placeholders={"addon_name": flasher_manager.addon_name},
        )

    async def async_step_flashing_complete(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Finish flashing and update the config entry."""
        flasher_manager = get_flasher_addon_manager(self.hass)
        await flasher_manager.async_uninstall_addon_waiting()

        # Finish ZHA migration if needed
        if self._zha_migration_mgr:
            try:
                await self._zha_migration_mgr.async_finish_migration()
            except Exception as err:
                _LOGGER.exception("Unexpected exception during ZHA migration")
                raise AbortFlow("zha_migration_failed") from err

        return self.async_create_entry(title="", data={})


async def check_multi_pan_addon(hass: HomeAssistant) -> None:
    """Check the multiprotocol addon state, and start it if installed but not started.

    Does nothing if Hass.io is not loaded.
    Raises on error or if the add-on is installed but not started.
    """
    if not is_hassio(hass):
        return

    multipan_manager = await get_multiprotocol_addon_manager(hass)
    try:
        addon_info: AddonInfo = await multipan_manager.async_get_addon_info()
    except AddonError as err:
        _LOGGER.error(err)
        raise HomeAssistantError from err

    # Request the addon to start if it's not started
    # `async_start_addon` returns as soon as the start request has been sent
    # and does not wait for the addon to be started, so we raise below
    if addon_info.state == AddonState.NOT_RUNNING:
        await multipan_manager.async_start_addon()

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

    multipan_manager = await get_multiprotocol_addon_manager(hass)
    addon_info: AddonInfo = await multipan_manager.async_get_addon_info()

    if addon_info.state != AddonState.RUNNING:
        return False

    if addon_info.options["device"] != device_path:
        return False

    return True
