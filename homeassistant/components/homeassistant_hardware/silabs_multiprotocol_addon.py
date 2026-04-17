"""Manage the Silicon Labs Multiprotocol add-on."""

from __future__ import annotations

from abc import ABC, abstractmethod
import asyncio
import dataclasses
import logging
from typing import Any, Protocol

from ha_silabs_firmware_client import FirmwareUpdateClient
import voluptuous as vol
import yarl

from homeassistant.components.hassio import (
    AddonError,
    AddonInfo,
    AddonManager,
    AddonState,
    hostname_from_addon_slug,
)
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlowResult,
    OptionsFlow,
    OptionsFlowManager,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import AbortFlow
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.hassio import is_hassio
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

from .const import LOGGER, SILABS_MULTIPROTOCOL_ADDON_SLUG
from .util import ApplicationType, WaitingAddonManager, async_flash_silabs_firmware

_LOGGER = logging.getLogger(__name__)

DATA_MULTIPROTOCOL_ADDON_MANAGER = "silabs_multiprotocol_addon_manager"


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
            self._hass,
            "silabs_multiprotocol",
            self._register_multipan_platform,
            wait_for_platforms=True,
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


class OptionsFlowHandler(OptionsFlow, ABC):
    """Handle an options flow for the Silicon Labs Multiprotocol add-on."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Set up the options flow."""
        # pylint: disable=hass-component-root-import
        from homeassistant.components.zha.radio_manager import (  # noqa: PLC0415
            ZhaMultiPANMigrationHelper,
        )

        self.install_task: asyncio.Task | None = None
        self.start_task: asyncio.Task | None = None
        self.stop_task: asyncio.Task | None = None
        self._zha_migration_mgr: ZhaMultiPANMigrationHelper | None = None
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

    @abstractmethod
    def _firmware_update_url(self) -> str:
        """Return the firmware update manifest URL."""

    @abstractmethod
    def _zigbee_firmware_type(self) -> str:
        """Return the zigbee firmware type identifier (e.g. 'yellow_zigbee_ncp')."""

    @property
    @abstractmethod
    def _flasher_cls(self) -> type:
        """Return the hardware-specific flasher class."""

    @property
    def flow_manager(self) -> OptionsFlowManager:
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
    ) -> ConfigFlowResult:
        """Manage the options."""
        if not is_hassio(self.hass):
            return self.async_abort(reason="not_hassio")

        return await self.async_step_on_supervisor()

    async def async_step_on_supervisor(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle logic when on Supervisor host."""
        multipan_manager = await get_multiprotocol_addon_manager(self.hass)
        addon_info = await self._async_get_addon_info(multipan_manager)

        if addon_info.state == AddonState.NOT_INSTALLED:
            return await self.async_step_addon_not_installed()
        return await self.async_step_addon_installed()

    async def async_step_addon_not_installed(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
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
    ) -> ConfigFlowResult:
        """Install Silicon Labs Multiprotocol add-on."""
        multipan_manager = await get_multiprotocol_addon_manager(self.hass)

        if not self.install_task:
            self.install_task = self.hass.async_create_task(
                multipan_manager.async_install_addon_waiting(),
                "SiLabs Multiprotocol addon install",
                eager_start=False,
            )

        if not self.install_task.done():
            return self.async_show_progress(
                step_id="install_addon",
                progress_action="install_addon",
                description_placeholders={"addon_name": multipan_manager.addon_name},
                progress_task=self.install_task,
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
    ) -> ConfigFlowResult:
        """Add-on installation failed."""
        multipan_manager = await get_multiprotocol_addon_manager(self.hass)
        return self.async_abort(
            reason="addon_install_failed",
            description_placeholders={"addon_name": multipan_manager.addon_name},
        )

    async def async_step_configure_addon(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure the Silicon Labs Multiprotocol add-on."""
        # pylint: disable=hass-component-root-import
        from homeassistant.components.zha import DOMAIN as ZHA_DOMAIN  # noqa: PLC0415
        from homeassistant.components.zha.radio_manager import (  # noqa: PLC0415
            ZhaMultiPANMigrationHelper,
        )
        from homeassistant.components.zha.silabs_multiprotocol import (  # noqa: PLC0415
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
    ) -> ConfigFlowResult:
        """Start Silicon Labs Multiprotocol add-on."""
        multipan_manager = await get_multiprotocol_addon_manager(self.hass)

        if not self.start_task:
            self.start_task = self.hass.async_create_task(
                multipan_manager.async_start_addon_waiting(), eager_start=False
            )

        if not self.start_task.done():
            return self.async_show_progress(
                step_id="start_addon",
                progress_action="start_addon",
                description_placeholders={"addon_name": multipan_manager.addon_name},
                progress_task=self.start_task,
            )

        try:
            await self.start_task
        except (AddonError, AbortFlow) as err:
            _LOGGER.error(err)
            return self.async_show_progress_done(next_step_id="start_failed")
        finally:
            self.start_task = None

        return self.async_show_progress_done(next_step_id="finish_addon_setup")

    async def async_step_start_failed(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Add-on start failed."""
        multipan_manager = await get_multiprotocol_addon_manager(self.hass)
        return self.async_abort(
            reason="addon_start_failed",
            description_placeholders={"addon_name": multipan_manager.addon_name},
        )

    async def async_step_finish_addon_setup(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Prepare info needed to complete the config entry update."""
        # Always reload entry after installing the addon.
        self.hass.async_create_task(
            self.hass.config_entries.async_reload(self.config_entry.entry_id),
            eager_start=False,
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
    ) -> ConfigFlowResult:
        """Show dialog explaining the addon is in use by another device."""
        if user_input is None:
            return self.async_show_form(step_id="addon_installed_other_device")
        return self.async_create_entry(title="", data={})

    async def async_step_addon_installed(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle logic when the addon is already installed."""
        multipan_manager = await get_multiprotocol_addon_manager(self.hass)
        addon_info = await self._async_get_addon_info(multipan_manager)

        serial_device = (await self._async_serial_port_settings()).device
        if addon_info.options.get(CONF_ADDON_DEVICE) != serial_device:
            return await self.async_step_addon_installed_other_device()
        return await self.async_step_addon_menu()

    async def async_step_addon_menu(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
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
    ) -> ConfigFlowResult:
        """Reconfigure the addon."""
        multipan_manager = await get_multiprotocol_addon_manager(self.hass)
        active_platforms = await multipan_manager.async_active_platforms()
        if set(active_platforms) != {"otbr", "zha"}:
            return await self.async_step_notify_unknown_multipan_user()
        return await self.async_step_change_channel()

    async def async_step_notify_unknown_multipan_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Notify that there may be unknown multipan platforms."""
        if user_input is None:
            return self.async_show_form(
                step_id="notify_unknown_multipan_user",
            )
        return await self.async_step_change_channel()

    async def async_step_change_channel(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
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
    ) -> ConfigFlowResult:
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
    ) -> ConfigFlowResult:
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
    ) -> ConfigFlowResult:
        """Initiate ZHA backup and start multiprotocol addon uninstall."""
        # pylint: disable=hass-component-root-import
        from homeassistant.components.zha import DOMAIN as ZHA_DOMAIN  # noqa: PLC0415
        from homeassistant.components.zha.radio_manager import (  # noqa: PLC0415
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

        return await self.async_step_uninstall_multiprotocol_addon()

    async def async_step_uninstall_multiprotocol_addon(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Uninstall Silicon Labs Multiprotocol add-on."""
        multipan_manager = await get_multiprotocol_addon_manager(self.hass)

        if not self.stop_task:
            self.stop_task = self.hass.async_create_task(
                multipan_manager.async_uninstall_addon_waiting(),
                "SiLabs Multiprotocol addon uninstall",
                eager_start=False,
            )

        if not self.stop_task.done():
            return self.async_show_progress(
                step_id="uninstall_multiprotocol_addon",
                progress_action="uninstall_multiprotocol_addon",
                description_placeholders={"addon_name": multipan_manager.addon_name},
                progress_task=self.stop_task,
            )

        try:
            await self.stop_task
        finally:
            self.stop_task = None

        return self.async_show_progress_done(next_step_id="install_zigbee_firmware")

    async def async_step_install_zigbee_firmware(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Flash Zigbee firmware directly onto the radio."""
        if not self.install_task:

            async def _flash_firmware() -> None:
                serial_port_settings = await self._async_serial_port_settings()
                device = serial_port_settings.device

                session = async_get_clientsession(self.hass)
                client = FirmwareUpdateClient(self._firmware_update_url(), session)

                manifest = await client.async_update_data()
                fw_manifest = next(
                    fw
                    for fw in manifest.firmwares
                    if fw.filename.startswith(self._zigbee_firmware_type())
                )

                fw_data = await client.async_fetch_firmware(fw_manifest)

                await async_flash_silabs_firmware(
                    hass=self.hass,
                    device=device,
                    fw_data=fw_data,
                    flasher_cls=self._flasher_cls,
                    expected_installed_firmware_type=ApplicationType.EZSP,
                )

            self.install_task = self.hass.async_create_task(
                _flash_firmware(),
                "Flash Zigbee firmware",
                eager_start=False,
            )

        if not self.install_task.done():
            return self.async_show_progress(
                step_id="install_zigbee_firmware",
                progress_action="install_zigbee_firmware",
                description_placeholders={
                    "hardware_name": self._hardware_name(),
                },
                progress_task=self.install_task,
            )

        try:
            await self.install_task
        except Exception:
            _LOGGER.exception("Failed to flash Zigbee firmware")
            return self.async_show_progress_done(next_step_id="firmware_flash_failed")
        finally:
            self.install_task = None

        return self.async_show_progress_done(next_step_id="flashing_complete")

    async def async_step_firmware_flash_failed(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Firmware flashing failed."""
        return self.async_abort(
            reason="fw_install_failed",
            description_placeholders={"hardware_name": self._hardware_name()},
        )

    async def async_step_flashing_complete(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Finish flashing and update the config entry."""
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
