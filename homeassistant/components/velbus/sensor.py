"""Support for Velbus sensors."""
from __future__ import annotations

from homeassistant.components.sensor import (
    STATE_CLASS_MEASUREMENT,
    STATE_CLASS_TOTAL_INCREASING,
    SensorEntity,
)
from homeassistant.const import (
    DEVICE_CLASS_ENERGY,
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_TEMPERATURE,
)

from . import VelbusEntity
from .const import DOMAIN


async def async_setup_entry(hass, entry, async_add_entities):
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

    def __init__(self, channel, counter=False):
        """Initialize a sensor Velbus entity."""
        super().__init__(channel)
        self._is_counter = counter

    @property
    def unique_id(self):
        """Return unique ID for counter sensors."""
        unique_id = super().unique_id
        if self._is_counter:
            unique_id = f"{unique_id}-counter"
        return unique_id

    @property
    def name(self):
        """Return the name for the sensor."""
        name = super().name
        if self._is_counter:
            name = f"{name}-counter"
        return name

    @property
    def device_class(self):
        """Return the device class of the sensor."""
        if self._is_counter:
            return DEVICE_CLASS_ENERGY
        if self._channel.is_counter_channel():
            return DEVICE_CLASS_POWER
        if self._channel.is_temperature():
            return DEVICE_CLASS_TEMPERATURE
        return None

    @property
    def native_value(self):
        """Return the state of the sensor."""
        if self._is_counter:
            return self._channel.get_counter_state()
        return self._channel.get_state()

    @property
    def native_unit_of_measurement(self):
        """Return the unit this state is expressed in."""
        if self._is_counter:
            return self._channel.get_counter_unit()
        return self._channel.get_unit()

    @property
    def icon(self):
        """Icon to use in the frontend."""
        if self._is_counter:
            return "mdi:counter"
        return None

    @property
    def state_class(self):
        """Return the state class of this device."""
        if self._is_counter:
            return STATE_CLASS_TOTAL_INCREASING
        return STATE_CLASS_MEASUREMENT
