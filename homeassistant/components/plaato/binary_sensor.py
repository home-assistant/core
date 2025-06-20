"""Support for Plaato Airlock sensors."""

from __future__ import annotations

from pyplaato.plaato import PlaatoKeg

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_USE_WEBHOOK, COORDINATOR, DOMAIN
from .entity import PlaatoEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Plaato from a config entry."""

    if config_entry.data[CONF_USE_WEBHOOK]:
        return

    coordinator = hass.data[DOMAIN][config_entry.entry_id][COORDINATOR]
    async_add_entities(
        PlaatoBinarySensor(
            hass.data[DOMAIN][config_entry.entry_id],
            sensor_type,
            coordinator,
        )
        for sensor_type in coordinator.data.binary_sensors
    )


class PlaatoBinarySensor(PlaatoEntity, BinarySensorEntity):
    """Representation of a Binary Sensor."""

    def __init__(self, data, sensor_type, coordinator=None) -> None:
        """Initialize plaato binary sensor."""
        super().__init__(data, sensor_type, coordinator)
        if sensor_type is PlaatoKeg.Pins.LEAK_DETECTION:
            self._attr_device_class = BinarySensorDeviceClass.PROBLEM
        elif sensor_type is PlaatoKeg.Pins.POURING:
            self._attr_device_class = BinarySensorDeviceClass.OPENING

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        if self._coordinator is not None:
            return self._coordinator.data.binary_sensors.get(self._sensor_type)
        return False
