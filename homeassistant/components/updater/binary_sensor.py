"""Support for Home Assistant Updater binary sensors."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import ATTR_NEWEST_VERSION, ATTR_RELEASE_NOTES, DOMAIN as UPDATER_DOMAIN


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the updater binary sensors."""
    if discovery_info is None:
        return

    async_add_entities([UpdaterBinary(hass.data[UPDATER_DOMAIN])])


class UpdaterBinary(CoordinatorEntity, BinarySensorEntity):
    """Representation of an updater binary sensor."""

    _attr_device_class = BinarySensorDeviceClass.UPDATE
    _attr_name = "Updater"
    _attr_unique_id = "updater"

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return True

    @property
    def is_on(self) -> bool:
        """Return true if there is an update available."""
        return self.coordinator.data and self.coordinator.data.update_available

    @property
    def extra_state_attributes(self) -> dict | None:
        """Return the optional state attributes."""
        if not self.coordinator.data:
            return None
        data = {}
        if self.coordinator.data.release_notes:
            data[ATTR_RELEASE_NOTES] = self.coordinator.data.release_notes
        if self.coordinator.data.newest_version:
            data[ATTR_NEWEST_VERSION] = self.coordinator.data.newest_version
        return data
