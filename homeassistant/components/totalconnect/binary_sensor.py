"""Interfaces with TotalConnect sensors."""
import logging

from homeassistant.components.binary_sensor import (BinarySensorDevice,
    DEVICE_CLASS_DOOR, DEVICE_CLASS_SMOKE, DEVICE_CLASS_GAS)

from total_connect_client.TotalConnectClient import (ZONE_TYPE_SECURITY,
    ZONE_TYPE_FIRE_SMOKE, ZONE_TYPE_CARBON_MONOXIDE,
    ZONE_STATUS_NORMAL, ZONE_STATUS_BYPASSED, ZONE_STATUS_FAULT,
    ZONE_STATUS_TAMPER, ZONE_STATUS_TROUBLE_LOW_BATTERY,
    ZONE_STATUS_TRIGGERED)

from . import DOMAIN as TOTALCONNECT_DOMAIN

_LOGGER = logging.getLogger(__name__)

# total_connect zone types mapped to binary_sensor class
SENSOR_TYPES = {
    ZONE_TYPE_SECURITY: DEVICE_CLASS_DOOR,
    ZONE_TYPE_FIRE_SMOKE: DEVICE_CLASS_SMOKE,
    ZONE_TYPE_CARBON_MONOXIDE: DEVICE_CLASS_GAS,
}


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up a sensor for a TotalConnect device."""
    if discovery_info is None:
        return

    sensors = []

    client_locations = hass.data[TOTALCONNECT_DOMAIN].client.locations

    for k in client_locations:
        for zone in client_locations[k].zones:
            sensors.append(TotalConnectBinarySensor(zone, k, client_locations))
    add_entities(sensors)


class TotalConnectBinarySensor(BinarySensorDevice):
    """Represent an TotalConnect zone."""

    def __init__(self, zone_id, location_id, locations):
        """Initialize the TotalConnect status."""
        self._zone_id = zone_id
        self._location_id = location_id
        self._locations = locations
        self._name = 'TC {} zone {}'.format(
            locations[location_id].location_name, zone_id)
        self._state = locations[location_id].zones[zone_id].status
        self._unique_id = 'TC {} zone {}'.format(
            locations[location_id].location_name, zone_id)
        self._device_class = locations[location_id].zones[zone_id].zone_type_id
        self._is_low_battery = False
        self._is_tampered = False
        self._is_on = False
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
        status = self._locations[self._location_id].zones[self._zone_id].status

        self._is_on = not status == ZONE_STATUS_BYPASSED
        self._is_tampered = (status == ZONE_STATUS_TAMPER)
        self._is_low_battery = (status == ZONE_STATUS_TROUBLE_LOW_BATTERY)

        if status == ZONE_STATUS_NORMAL:
            self._state = False
        elif status in (ZONE_STATUS_FAULT, ZONE_STATUS_TRIGGERED):
            self._state = True
        else:
            self._state = False
            _LOGGER.info('Unknown Total Connect zone status %s returned.',
                         status)

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return self._is_on

    @property
    def device_class(self):
        """Return the class of this device, from component DEVICE_CLASSES."""
        return SENSOR_TYPES.get(self._device_class)

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
