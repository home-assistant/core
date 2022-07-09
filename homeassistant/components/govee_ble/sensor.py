"""Support for govee ble sensors."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant import config_entries
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    TEMP_CELSIUS,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .bluetooth_update_coordinator import (
    BluetoothCoordinatorEntity,
    BluetoothDataUpdateCoordinator,
)
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SENSOR_TYPES: dict[str, SensorEntityDescription] = {
    "temperature": SensorEntityDescription(
        key="temperature",
        name="Temperature",
        native_unit_of_measurement=TEMP_CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "humidity": SensorEntityDescription(
        key="humidity",
        name="Humidity",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "battery": SensorEntityDescription(
        key="battery",
        name="Battery",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "rssi": SensorEntityDescription(
        key="rssi",
        name="RSSI",
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
    ),
}
ALL_SENSORS = set(SENSOR_TYPES)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: config_entries.ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Govee BLE sensors."""
    coordinator: BluetoothDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    created: set[str] = set()

    @callback
    def _async_add_or_update_entities(data: dict[str, Any]) -> None:
        """Listen for new entities."""
        possible_sensors = ALL_SENSORS.intersection(data)
        new = possible_sensors.difference(created)
        if new:
            created.update(new)
            async_add_entities(
                GoveeSensor(coordinator, SENSOR_TYPES[key], data) for key in new
            )

    coordinator.async_add_listener(_async_add_or_update_entities)


class GoveeSensor(BluetoothCoordinatorEntity, SensorEntity):
    """Representation of a govee ble sensor."""

    entity_description: SensorEntityDescription

    @property
    def native_value(self) -> int | None:
        """Return the native value."""
        return self.data[self.entity_description.key]
