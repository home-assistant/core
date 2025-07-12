"""Sensor for max heating time."""

from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import HuumDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up max time sensor."""
    async_add_entities(
        [HuumTimerSensor(hass.data[DOMAIN][entry.entry_id], entry.entry_id)],
        True,
    )


class HuumTimerSensor(CoordinatorEntity[HuumDataUpdateCoordinator], SensorEntity):
    """Representation of a Sensor."""

    _attr_has_entity_name = True
    _attr_name = "Max heating time"
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = "h"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: HuumDataUpdateCoordinator, unique_id: str) -> None:
        """Initialize the Sensor."""
        CoordinatorEntity.__init__(self, coordinator)

        self._attr_unique_id = f"{unique_id}_light"
        self._attr_device_info = coordinator.device_info

        self._coordinator = coordinator

    @property
    def native_value(self) -> int | None:
        """Return the current value."""
        return self._coordinator.data.sauna_config.max_heating_time
