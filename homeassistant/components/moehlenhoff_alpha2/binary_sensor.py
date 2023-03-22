"""Support for Alpha2 IO device battery sensors."""

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import Alpha2BaseCoordinator
from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add Alpha2 sensor entities from a config_entry."""

    coordinator: Alpha2BaseCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    async_add_entities(
        Alpha2IODeviceBatterySensor(coordinator, io_device_id)
        for io_device_id, io_device in coordinator.data["io_devices"].items()
        if io_device["_HEATAREA_ID"]
    )


class Alpha2IODeviceBatterySensor(
    CoordinatorEntity[Alpha2BaseCoordinator], BinarySensorEntity
):
    """Alpha2 IO device battery binary sensor."""

    _attr_device_class = BinarySensorDeviceClass.BATTERY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: Alpha2BaseCoordinator, io_device_id: str) -> None:
        """Initialize Alpha2IODeviceBatterySensor."""
        super().__init__(coordinator)
        self.io_device_id = io_device_id
        self._attr_unique_id = f"{io_device_id}:battery"
        io_device = self.coordinator.data["io_devices"][io_device_id]
        heat_area = self.coordinator.data["heat_areas"][io_device["_HEATAREA_ID"]]
        self._attr_name = (
            f"{heat_area['HEATAREA_NAME']} IO device {io_device['NR']} battery"
        )

    @property
    def is_on(self):
        """Return the state of the sensor."""
        # 0=empty, 1=weak, 2=good
        return self.coordinator.data["io_devices"][self.io_device_id]["BATTERY"] < 2
