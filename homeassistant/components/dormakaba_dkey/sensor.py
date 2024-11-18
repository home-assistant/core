"""Dormakaba dKey integration sensor platform."""

from __future__ import annotations

from py_dormakaba_dkey import DKEYLock

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN
from .entity import DormakabaDkeyEntity
from .models import DormakabaDkeyData

BINARY_SENSOR_DESCRIPTIONS = (
    SensorEntityDescription(
        key="battery_level",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the lock platform for Dormakaba dKey."""
    data: DormakabaDkeyData = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        DormakabaDkeySensor(data.coordinator, data.lock, description)
        for description in BINARY_SENSOR_DESCRIPTIONS
    )


class DormakabaDkeySensor(DormakabaDkeyEntity, SensorEntity):
    """Dormakaba dKey sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[None],
        lock: DKEYLock,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize a Dormakaba dKey binary sensor."""
        self.entity_description = description
        self._attr_unique_id = f"{lock.address}_{description.key}"
        super().__init__(coordinator, lock)

    @callback
    def _async_update_attrs(self) -> None:
        """Handle updating _attr values."""
        self._attr_native_value = getattr(self._lock, self.entity_description.key)
