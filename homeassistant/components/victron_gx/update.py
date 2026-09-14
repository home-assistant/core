"""Firmware updates for Victron GX devices."""

from datetime import timedelta
import logging
from typing import Any, override

from victron_mqtt import FirmwareUpdateError

from homeassistant.components.update import (
    UpdateDeviceClass,
    UpdateEntity,
    UpdateEntityFeature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .hub import VictronGxConfigEntry

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1
SCAN_INTERVAL = timedelta(seconds=30)

_FIRMWARE_UPDATE_URL = "https://www.victronenergy.com/blog/category/firmware-software/"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: VictronGxConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the GX firmware update entity."""
    async_add_entities([VictronFirmwareUpdateEntity(config_entry)], True)


class VictronFirmwareUpdateEntity(UpdateEntity):
    """Represent the Venus OS firmware installed on a GX device."""

    _attr_device_class = UpdateDeviceClass.FIRMWARE
    _attr_has_entity_name = True
    _attr_release_url = _FIRMWARE_UPDATE_URL
    _attr_should_poll = True
    _attr_supported_features = (
        UpdateEntityFeature.INSTALL | UpdateEntityFeature.PROGRESS
    )
    _attr_translation_key = "venus_os_firmware"

    def __init__(self, entry: VictronGxConfigEntry) -> None:
        """Initialize the firmware update entity."""
        self._hub = entry.runtime_data
        info = self._hub.firmware_update_info
        self._installed_version = info.installed_version
        self._online_version = info.available_version
        self._attr_unique_id = f"{entry.unique_id}_firmware"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.unique_id}_system_0")}
        )

    @property
    @override
    def installed_version(self) -> str | None:
        """Return the installed Venus OS version."""
        return self._installed_version

    @property
    @override
    def latest_version(self) -> str | None:
        """Return the latest available Venus OS version."""
        return self._online_version or self._installed_version

    @property
    @override
    def available(self) -> bool:
        """Return whether the installed firmware version is available."""
        return self.installed_version is not None

    @override
    def version_is_newer(self, latest_version: str, installed_version: str) -> bool:
        """Return whether Victron offers a Venus OS firmware build."""
        return self._online_version is not None

    @override
    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        """Install the latest Venus OS firmware."""
        latest_version = self._online_version
        if latest_version is None:
            return

        self._attr_in_progress = True
        self.async_write_ha_state()

        @callback
        def _async_update_progress(progress: int) -> None:
            self._attr_update_percentage = progress
            self.async_write_ha_state()

        try:
            try:
                await self._hub.install_firmware_update(_async_update_progress)
            except FirmwareUpdateError as err:
                _LOGGER.warning("GX firmware installation failed: %s", err.reason)
        finally:
            self._attr_in_progress = False
            self._attr_update_percentage = None
            self.async_write_ha_state()

    async def async_update(self) -> None:
        """Refresh the entity from the latest in-memory MQTT values."""
        info = self._hub.firmware_update_info
        self._installed_version = info.installed_version
        self._online_version = info.available_version
        self._attr_in_progress = info.in_progress
        self._attr_update_percentage = info.progress if info.in_progress else None
