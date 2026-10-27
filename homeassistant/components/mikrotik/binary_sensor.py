"""Support for binary sensors."""

from typing import Final, override

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import MikrotikConfigEntry
from .entity import MikrotikDeviceEntity

# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0


BINARY_SENSOR_TYPES: Final = {
    BinarySensorEntityDescription(
        key="running",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MikrotikConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up binary sensor entities for Mikrotik Devices."""

    coordinator = entry.runtime_data

    binary_sensors_list = [
        MikrotikBinarySensorEntity(entry, coordinator, binary_sensor_desc, interface)
        for binary_sensor_desc in BINARY_SENSOR_TYPES
        for interface in coordinator.api.interfaces
        if interface.get(binary_sensor_desc.key) is not None
    ]

    async_add_entities(binary_sensors_list)


class MikrotikBinarySensorEntity(MikrotikDeviceEntity, BinarySensorEntity):
    """Binary sensor entity for Mikrotik."""

    @property
    @override
    def is_on(self) -> bool | None:
        """Return the state of the binary sensor."""
        return self._interface.get(self.entity_description.key)
