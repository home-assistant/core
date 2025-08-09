"""Sensor platform for Linea Research integration."""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import SIGNAL_STRENGTH_DECIBELS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import LineaResearchConfigEntry
from .entity import LineaResearchEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: LineaResearchConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Linea Research sensors from a config entry."""
    coordinator = config_entry.runtime_data
    
    async_add_entities([
        LineaResearchGainASensor(coordinator),
        LineaResearchGainBSensor(coordinator),
    ])


class LineaResearchGainASensor(LineaResearchEntity, SensorEntity):
    """Representation of a Linea Research amplifier gain for channel A."""

    def __init__(self, coordinator: LineaResearchConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, "gain_a")
        self._attr_name = "Channel A gain"
        self._attr_device_class = SensorDeviceClass.SIGNAL_STRENGTH
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = SIGNAL_STRENGTH_DECIBELS
        self._attr_icon = "mdi:volume-high"

    @property
    def native_value(self) -> float | None:
        """Return the gain value for channel A."""
        return self.coordinator.data.get("gain_a")


class LineaResearchGainBSensor(LineaResearchEntity, SensorEntity):
    """Representation of a Linea Research amplifier gain for channel B."""

    def __init__(self, coordinator: LineaResearchConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, "gain_b")
        self._attr_name = "Channel B gain"
        self._attr_device_class = SensorDeviceClass.SIGNAL_STRENGTH
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = SIGNAL_STRENGTH_DECIBELS
        self._attr_icon = "mdi:volume-high"

    @property
    def native_value(self) -> float | None:
        """Return the gain value for channel B."""
        return self.coordinator.data.get("gain_b")