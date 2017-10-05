"""
Loxone simple sensor

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/loxone/
"""

import logging
from homeassistant.helpers.entity import Entity
from homeassistant.const import (CONF_UNIT_OF_MEASUREMENT)

DOMAIN = 'loxone'
EVENT = 'loxone_received'

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices):
    """Setup the sensor platform."""
    sensor_name = config.get("sensorname")
    uuid = config.get("uuid")
    sensor_typ = config.get("sensortyp")
    unit_of_measurement = config.get(CONF_UNIT_OF_MEASUREMENT)
    sensor = Loxonesensor(sensor_name, uuid, sensor_typ, unit_of_measurement)
    add_devices([sensor])
    hass.bus.listen(EVENT, sensor.event_handler)


class Loxonesensor(Entity):
    """Representation of a Sensor."""

    def __init__(self, name, uuid, sensor_typ, unit_of_measurement):
        """Initialize the sensor."""
        self._state = 0.0
        self._name = name
        self._uuid = uuid
        self._sensor_typ = sensor_typ
        self._unit_of_measurement = unit_of_measurement

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def should_poll(self):
        """ Disable polling"""
        return False

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit_of_measurement

    def event_handler(self, event):
        """ Event_handler """
        if self._uuid in event.data:
            if self._sensor_typ == "InfoOnlyAnalog":
                self._state = round(event.data[self._uuid], 1)
            elif self._sensor_typ == "InfoOnlyDigital":
                self._state = event.data[self._uuid]
                if self._state == 1:
                    self._state = "on"
                else:
                    self._state = "off"
            else:
                self._state = event.data[self._uuid]
            self.update()
            self.schedule_update_ha_state()
