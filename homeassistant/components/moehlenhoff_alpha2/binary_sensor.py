"""Support for Alpha2 IO device battery sensors."""

from typing import override

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import Alpha2BaseCoordinator, Alpha2ConfigEntry
from .entity import Alpha2RoomEntity

BATTERY_DESCRIPTION = BinarySensorEntityDescription(
    key="battery",
    translation_key="battery",
    name="Battery",
    device_class=BinarySensorDeviceClass.BATTERY,
    entity_category=EntityCategory.DIAGNOSTIC,
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: Alpha2ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add Alpha2 sensor entities from a config_entry."""

    coordinator = config_entry.runtime_data

    async_add_entities(
        Alpha2IODeviceBatterySensor(coordinator, io_device_id)
        for io_device_id, io_device in coordinator.data["io_devices"].items()
        if io_device["_HEATAREA_ID"]
        and io_device["_HEATAREA_ID"] in coordinator.data["heat_areas"]
    )


class Alpha2IODeviceBatterySensor(Alpha2RoomEntity, BinarySensorEntity):
    """Alpha2 IO device battery binary sensor."""

    def __init__(self, coordinator: Alpha2BaseCoordinator, io_device_id: str) -> None:
        """Initialize Alpha2IODeviceBatterySensor."""
        io_device = coordinator.data["io_devices"][io_device_id]
        super().__init__(coordinator, io_device["_HEATAREA_ID"])
        self.entity_description = BATTERY_DESCRIPTION
        self.io_device_id = io_device_id
        self._attr_unique_id = f"{io_device_id}:battery"

    @property
    @override
    def is_on(self) -> bool:
        """Return the state of the sensor."""
        # 0=empty, 1=weak, 2=good
        return self.coordinator.data["io_devices"][self.io_device_id]["BATTERY"] < 2
