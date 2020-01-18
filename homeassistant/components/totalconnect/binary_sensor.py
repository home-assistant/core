"""Interfaces with TotalConnect sensors."""
import logging

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_DOOR,
    DEVICE_CLASS_GAS,
    DEVICE_CLASS_SMOKE,
    BinarySensorDevice,
)

from . import DOMAIN as TOTALCONNECT_DOMAIN

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up a sensor for a TotalConnect device."""
    if discovery_info is None:
        return

    sensors = []

    client_locations = hass.data[TOTALCONNECT_DOMAIN].client.locations

    for location_id in client_locations:
        for zone in client_locations[location_id].zones:
            sensors.append(TotalConnectBinarySensor(zone, location_id, client_locations))
    add_entities(sensors)


class TotalConnectBinarySensor(BinarySensorDevice):
    """Represent an TotalConnect zone."""

    def __init__(self, zone_id, location_id, locations):
        """Initialize the TotalConnect status."""
        self._zone_id = zone_id
        self._location_id = location_id
        self._name = "TC {} zone {}".format(
            locations[location_id].location_name, zone_id
        )
        self._unique_id = "TC {} zone {}".format(
            locations[location_id].location_name, zone_id
        )
        self._zone = locations[location_id].zones[zone_id]
        self.update()

    @property
    def unique_id(self) -> str:
        """Return the unique id."""
        return self._unique_id

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    def update(self):
        """Return the state of the device."""
        self._is_on = not self._zone.is_bypassed()
        self._is_tampered = self._zone.is_tampered()
        self._is_low_battery = self._zone.is_low_battery()

        if self._zone.is_faulted() or self._zone.is_triggered():
            self._state = True
        else:
            self._state = False

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
        _LOGGER.info(
            "Unknown Total Connect zone type %s returned by zone %s.",
            self._zone.zone_type_id,
            self._zone_id,
        )
        return None

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        attributes = {}
        attributes["zone_id"] = self._zone_id
        attributes["zone_description"] = self._name
        attributes["location_id"] = self._location_id
        attributes["low_battery"] = self._is_low_battery
        attributes["tampered"] = self._is_tampered
        return attributes
