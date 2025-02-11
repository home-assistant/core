"""Support for Velbus sensors."""

from __future__ import annotations

from velbusaio.channels import ButtonCounter, LightSensor, SensorNumber, Temperature

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import VelbusConfigEntry
from .entity import VelbusEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VelbusConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Velbus switch based on config_entry."""
    await entry.runtime_data.scan_task
    entities = []
    for channel in entry.runtime_data.controller.get_all_sensor():
        entities.append(VelbusSensor(channel))
        if channel.is_counter_channel():
            entities.append(VelbusSensor(channel, True))
    async_add_entities(entities)


class VelbusSensor(VelbusEntity, SensorEntity):
    """Representation of a sensor."""

    _channel: ButtonCounter | Temperature | LightSensor | SensorNumber

    def __init__(
        self,
        channel: ButtonCounter | Temperature | LightSensor | SensorNumber,
        counter: bool = False,
    ) -> None:
        """Initialize a sensor Velbus entity."""
        super().__init__(channel)
        self._is_counter: bool = counter
        if self._is_counter:
            self._attr_device_class = SensorDeviceClass.ENERGY
            self._attr_icon = "mdi:counter"
            self._attr_name = f"{self._attr_name}-counter"
            self._attr_state_class = SensorStateClass.TOTAL_INCREASING
            self._attr_unique_id = f"{self._attr_unique_id}-counter"
        elif channel.is_counter_channel():
            self._attr_device_class = SensorDeviceClass.POWER
            self._attr_state_class = SensorStateClass.MEASUREMENT
        elif channel.is_temperature():
            self._attr_device_class = SensorDeviceClass.TEMPERATURE
            self._attr_state_class = SensorStateClass.MEASUREMENT
        else:
            self._attr_state_class = SensorStateClass.MEASUREMENT
        # unit
        if self._is_counter:
            self._attr_native_unit_of_measurement = channel.get_counter_unit()
        else:
            self._attr_native_unit_of_measurement = channel.get_unit()

    @property
    def native_value(self) -> float | int | None:
        """Return the state of the sensor."""
        if self._is_counter:
            return float(self._channel.get_counter_state())
        return float(self._channel.get_state())
