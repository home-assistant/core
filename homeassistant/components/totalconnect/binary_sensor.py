"""Interfaces with TotalConnect sensors."""
import logging

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_DOOR,
    DEVICE_CLASS_GAS,
    DEVICE_CLASS_SMOKE,
    BinarySensorEntity,
)

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    """Set up TotalConnect device sensors based on a config entry."""
    sensors = []

    client_locations = hass.data[DOMAIN][entry.entry_id].locations

    for location_id, location in client_locations.items():
        for zone_id, zone in location.zones.items():
            sensors.append(TotalConnectBinarySensor(zone_id, location_id, zone))

    async_add_entities(sensors, True)


class TotalConnectBinarySensor(BinarySensorEntity):
    """Represent an TotalConnect zone."""

    def __init__(self, zone_id, location_id, zone):
        """Initialize the TotalConnect status."""
        self._zone_id = zone_id
        self._location_id = location_id
        self._zone = zone
        self._name = self._zone.description
        self._unique_id = f"{location_id} {zone_id}"
        self._is_on = None
        self._is_tampered = None
        self._is_low_battery = None

    @property
    def unique_id(self):
        """Return the unique id."""
        return self._unique_id

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    def update(self):
        """Return the state of the device."""
        self._is_tampered = self._zone.is_tampered()
        self._is_low_battery = self._zone.is_low_battery()

        if self._zone.is_faulted() or self._zone.is_triggered():
            self._is_on = True
        else:
            self._is_on = False

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return self._is_on

    @property
    def device_class(self):
        """Return the class of this device, from component DEVICE_CLASSES."""
        if self._zone.is_type_security():
            return DEVICE_CLASS_DOOR
        if self._zone.is_type_fire():
            return DEVICE_CLASS_SMOKE
        if self._zone.is_type_carbon_monoxide():
            return DEVICE_CLASS_GAS
        return None

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        attributes = {
            "zone_id": self._zone_id,
            "location_id": self._location_id,
            "low_battery": self._is_low_battery,
            "tampered": self._is_tampered,
        }
        return attributes
