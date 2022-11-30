"""Support for Velbus sensors."""
from __future__ import annotations

from velbusaio.channels import ButtonCounter, LightSensor, SensorNumber, Temperature

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import VelbusEntity
from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Velbus switch based on config_entry."""
    await hass.data[DOMAIN][entry.entry_id]["tsk"]
    cntrl = hass.data[DOMAIN][entry.entry_id]["cntrl"]
    entities = []
    for channel in cntrl.get_all("sensor"):
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
        # define the unique id
        if self._is_counter:
            self._attr_unique_id = f"{self._attr_unique_id}-counter"
        # define the name
        if self._is_counter:
            self._attr_name = f"{self._attr_name}-counter"
        # define the device class
        if self._is_counter:
            self._attr_device_class = SensorDeviceClass.POWER
        elif channel.is_counter_channel():
            self._attr_device_class = SensorDeviceClass.ENERGY
        elif channel.is_temperature():
            self._attr_device_class = SensorDeviceClass.TEMPERATURE
        # define the icon
        if self._is_counter:
            self._attr_icon = "mdi:counter"
        # the state class
        if self._is_counter:
            self._attr_state_class = SensorStateClass.TOTAL_INCREASING
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
