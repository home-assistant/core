"""Support for the ZHA platform."""

from __future__ import annotations

from homeassistant.components.device_tracker import ScannerEntity, SourceType
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import ZHAEntity
from .helpers import get_zha_data


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Zigbee Home Automation device tracker from config entry."""
    zha_data = get_zha_data(hass)
    entities_to_create = zha_data.platforms.pop(Platform.DEVICE_TRACKER, [])
    entities = [
        ZHADeviceScannerEntity(entity_data) for entity_data in entities_to_create
    ]
    async_add_entities(entities)


class ZHADeviceScannerEntity(ScannerEntity, ZHAEntity):
    """Represent a tracked device."""

    _attr_should_poll = True  # BaseZhaEntity defaults to False
    _attr_name: str = "Device scanner"

    @property
    def is_connected(self) -> bool:
        """Return true if the device is connected to the network."""
        return self.entity_data.entity.is_connected

    @property
    def source_type(self) -> SourceType:
        """Return the source type, eg gps or router, of the device."""
        return SourceType.ROUTER

    @property
    def battery_level(self) -> int | None:
        """Return the battery level of the device.

        Percentage from 0-100.
        """
        return self.entity_data.entity.battery_level

    @property  # type: ignore[misc]
    def device_info(
        self,
    ) -> DeviceInfo:
        """Return device info."""
        # We opt ZHA device tracker back into overriding this method because
        # it doesn't track IP-based devices.
        # Call Super because ScannerEntity overrode it.
        # mypy doesn't know about fget: https://github.com/python/mypy/issues/6185
        return ZHAEntity.device_info.fget(self)  # type: ignore[attr-defined]

    @property
    def unique_id(self) -> str:
        """Return unique ID."""
        # Call Super because ScannerEntity overrode it.
        # mypy doesn't know about fget: https://github.com/python/mypy/issues/6185
        return ZHAEntity.unique_id.fget(self)  # type: ignore[attr-defined]
