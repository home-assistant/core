"""Sensor for max heating time."""

from __future__ import annotations

from huum.huum import Huum

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up max time sensor."""
    data = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [HuumTimerSensor(data.get("coordinator"), data.get("huum"), entry.entry_id)],
        True,
    )


class HuumTimerSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Sensor."""

    _attr_has_entity_name = True
    _attr_name = "Max heating time"
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = "h"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self, coordinator: CoordinatorEntity, huum: Huum, unique_id: str
    ) -> None:
        """Initialize the Sensor."""
        CoordinatorEntity.__init__(self, coordinator)

        self._attr_unique_id = f"{unique_id}_light"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_id)},
            name="Huum sauna",
            manufacturer="Huum",
            model="UKU WiFi",
            serial_number=coordinator.data.sauna_name,
        )

        self._huum = huum
        self._coordinator = coordinator

    @property
    def native_value(self) -> int | None:
        """Return the current value."""
        return self._coordinator.data.sauna_config.max_heating_time
