"""Binary sensor platform for Linea Research integration."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import LineaResearchConfigEntry
from .entity import LineaResearchEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: LineaResearchConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Linea Research binary sensors from a config entry."""
    coordinator = config_entry.runtime_data
    
    async_add_entities([
        LineaResearchSleepStateSensor(coordinator),
        LineaResearchMuteASensor(coordinator),
        LineaResearchMuteBSensor(coordinator),
    ])


class LineaResearchSleepStateSensor(LineaResearchEntity, BinarySensorEntity):
    """Representation of a Linea Research amplifier sleep state sensor."""

    def __init__(self, coordinator: LineaResearchConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, "sleep_state")
        self._attr_name = "Sleep state"
        self._attr_device_class = BinarySensorDeviceClass.RUNNING
        self._attr_icon = "mdi:sleep"

    @property
    def is_on(self) -> bool:
        """Return true if the amplifier is in sleep/standby mode."""
        # standby=True means the device is sleeping/off
        return self.coordinator.data.get("standby", True)


class LineaResearchMuteASensor(LineaResearchEntity, BinarySensorEntity):
    """Representation of a Linea Research amplifier mute state for channel A."""

    def __init__(self, coordinator: LineaResearchConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, "mute_a")
        self._attr_name = "Channel A mute"
        self._attr_device_class = BinarySensorDeviceClass.SOUND
        self._attr_icon = "mdi:volume-off"

    @property
    def is_on(self) -> bool:
        """Return true if channel A is muted."""
        return self.coordinator.data.get("mute_a", False)


class LineaResearchMuteBSensor(LineaResearchEntity, BinarySensorEntity):
    """Representation of a Linea Research amplifier mute state for channel B."""

    def __init__(self, coordinator: LineaResearchConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, "mute_b")
        self._attr_name = "Channel B mute"
        self._attr_device_class = BinarySensorDeviceClass.SOUND
        self._attr_icon = "mdi:volume-off"

    @property
    def is_on(self) -> bool:
        """Return true if channel B is muted."""
        return self.coordinator.data.get("mute_b", False)