"""Sensor for PSS BLE Scanner."""
from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

import logging
_LOGGER = logging.getLogger(__name__)

def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None
) -> None:
    """Set up the sensor platform."""
    _LOGGER.warning(str(discovery_info))
    _LOGGER.warning(str(config))
    _LOGGER.warning(str(add_entities))
    add_entities([PSSBLEScannerSensor()])

class PSSBLEScannerSensor(SensorEntity):
    """Representation of a PSS BLE Scanner sensor."""

    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_native_unit_of_measurement = "%"

    def __init__(self):
        """Initialize the sensor."""
        self._name = "PSS"

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    def update_state(self, data):
        """Update the state with new data."""
        _LOGGER.warning(str(data))
        self._attr_native_value = data
        self.async_write_ha_state()
