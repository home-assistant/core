"""Representation of Z-Wave updates."""
from __future__ import annotations

from collections.abc import Mapping
from datetime import timedelta
from typing import Any

from awesomeversion import AwesomeVersion
from zwave_js_server.client import Client as ZwaveClient
from zwave_js_server.exceptions import BaseZwaveJSServerError
from zwave_js_server.model.driver import Driver
from zwave_js_server.model.firmware import FirmwareUpdateInfo
from zwave_js_server.model.node import Node as ZwaveNode

from homeassistant.components.update import UpdateDeviceClass, UpdateEntity
from homeassistant.components.update.const import UpdateEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import API_KEY_FIRMWARE_UPDATE_SERVICE, DATA_CLIENT, DOMAIN, LOGGER
from .helpers import get_device_id, get_valueless_base_unique_id

PARALLEL_UPDATES = 1
SCAN_INTERVAL = timedelta(days=1)

ATTR_AVAILABLE_FIRMWARE_UPDATES = "available_firmware_updates"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Z-Wave button from config entry."""
    client: ZwaveClient = hass.data[DOMAIN][config_entry.entry_id][DATA_CLIENT]

    @callback
    def async_add_firmware_update_entity(node: ZwaveNode) -> None:
        """Add firmware update entity."""
        driver = client.driver
        assert driver is not None  # Driver is ready before platforms are loaded.
        async_add_entities([ZWaveNodeFirmwareUpdate(driver, node)], True)

    config_entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            f"{DOMAIN}_{config_entry.entry_id}_add_firmware_update_entity",
            async_add_firmware_update_entity,
        )
    )


def get_latest_firmware(
    firmwares: list[FirmwareUpdateInfo],
) -> FirmwareUpdateInfo:
    """Get the latest firmware from the available updates."""
    latest_firmware = FirmwareUpdateInfo("0.0.0", "", [])
    for firmware in firmwares:
        if AwesomeVersion(firmware.version) > AwesomeVersion(latest_firmware.version):
            latest_firmware = firmware
    return latest_firmware


class ZWaveNodeFirmwareUpdate(UpdateEntity):
    """Representation of a firmware update entity."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_device_class = UpdateDeviceClass.FIRMWARE
    _attr_supported_features = (
        UpdateEntityFeature.INSTALL
        | UpdateEntityFeature.RELEASE_NOTES
        | UpdateEntityFeature.SPECIFIC_VERSION
    )
    _attr_has_entity_name = True

    def __init__(self, driver: Driver, node: ZwaveNode) -> None:
        """Initialize a Z-Wave device firmware update entity."""
        self.driver = driver
        self.node = node
        self.available_firmware_updates: list[FirmwareUpdateInfo] = []
        self._latest_version_firmware: FirmwareUpdateInfo | None = None

        # Entity class attributes
        self._attr_name = "Firmware"
        self._base_unique_id = get_valueless_base_unique_id(driver, node)
        self._attr_unique_id = f"{self._base_unique_id}.firmware_update"
        # device may not be precreated in main handler yet
        self._attr_device_info = DeviceInfo(
            identifiers={get_device_id(driver, node)},
            sw_version=node.firmware_version,
            name=node.name or node.device_config.description or f"Node {node.node_id}",
            model=node.device_config.label,
            manufacturer=node.device_config.manufacturer,
            suggested_area=node.location if node.location else None,
        )

        self._attr_installed_version = self._attr_latest_version = node.firmware_version

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return entity specific state attributes."""

        return {
            ATTR_AVAILABLE_FIRMWARE_UPDATES: [
                firmware.version
                for firmware in sorted(
                    self.available_firmware_updates,
                    key=lambda f: AwesomeVersion(f.version),
                )
            ]
        }

    async def async_update(self) -> None:
        """Update the entity."""
        self.available_firmware_updates = (
            await self.driver.controller.async_get_available_firmware_updates(
                self.node, API_KEY_FIRMWARE_UPDATE_SERVICE
            )
        )
        self._async_process_updates(False)

    @callback
    def _async_process_updates(self, write_state: bool = True) -> None:
        """Process updates."""
        if self.available_firmware_updates:
            self._latest_version_firmware = firmware = get_latest_firmware(
                self.available_firmware_updates
            )
            self._attr_latest_version = firmware.version
        else:
            self._latest_version_firmware = None
            self._attr_latest_version = self._attr_installed_version
        if write_state:
            self.async_write_ha_state()

    async def async_release_notes(self) -> str | None:
        """Get release notes."""
        if self._latest_version_firmware is None:
            return None
        return self._latest_version_firmware.changelog

    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        """Install an update."""
        if version is None and self._latest_version_firmware:
            firmware = self._latest_version_firmware
        else:
            try:
                firmware = next(
                    firmware
                    for firmware in self.available_firmware_updates
                    if firmware.version == version
                )
            except StopIteration as err:
                raise ValueError(f"Version {version} not found") from err
        self._attr_in_progress = True
        try:
            for file in firmware.files:
                await self.driver.controller.async_begin_ota_firmware_update(
                    self.node, file
                )
        except BaseZwaveJSServerError as err:
            raise HomeAssistantError(err) from err
        else:
            self._attr_installed_version = firmware.version
            self.available_firmware_updates.remove(firmware)
            self._async_process_updates()
        finally:
            self._attr_in_progress = False

    async def async_poll_value(self, _: bool) -> None:
        """Poll a value."""
        LOGGER.error(
            "There is no value to refresh for this entity so the zwave_js.refresh_value "
            "service won't work for it"
        )

    async def async_added_to_hass(self) -> None:
        """Call when entity is added."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{DOMAIN}_{self.unique_id}_poll_value",
                self.async_poll_value,
            )
        )

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{DOMAIN}_{self._base_unique_id}_remove_entity",
                self.async_remove,
            )
        )
