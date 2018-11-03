"""
Support for Homekit sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.homekit_controller/
"""
import logging

from homeassistant.components.homekit_controller import (HomeKitEntity,
                                                         KNOWN_ACCESSORIES)

DEPENDENCIES = ['homekit_controller']

CHARACTERISTICS = {
    '4aaaf931-0dec-11e5-b939-0800200c9a66': {
        'title': 'realtime_energy',
        'units': 'Wh'
    },
    '4aaaf932-0dec-11e5-b939-0800200c9a66': {
        'title': 'current_hour_data',
        'units': 'Wh'
    },
    '4aaaf93f-0dec-11e5-b939-0800200c9a66': {
        'title': 'running_time',
        'units': 's'
    },
}

SERVICE_DEFAULT_CHARACTERISTIC = {
    '4aaaf930-0dec-11e5-b939-0800200c9a66': 'realtime_energy'
}

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up HomeKit sensor support."""
    if discovery_info is not None:
        accessory = hass.data[KNOWN_ACCESSORIES][discovery_info['serial']]
        add_entities([HomeKitSensor(accessory, discovery_info)],
                     True)


class HomeKitSensor(HomeKitEntity):
    """Representation of a HomeKit sensor."""

    def __init__(self, *args):
        """Initialise the sensor."""
        super().__init__(*args)
        self._sensor_data = {}
        self._state = None
        self._unit_of_measurement = None
        self._defaultc = SERVICE_DEFAULT_CHARACTERISTIC.get(self._type, None)

    def update_characteristics(self, characteristics):
        """Synchronise the sensor state with Home Assistant."""

        for characteristic in characteristics:
            ctype = CHARACTERISTICS.get(characteristic['type'], None)
            if ctype is not None:
                dataValue = characteristic['value']
                self._sensor_data[ctype['title']] = dataValue
                self._sensor_data[ctype['title'] + '_unit'] = ctype['units']

                if self._defaultc is not None \
                        and ctype['title'] == self._defaultc:
                    self._state = dataValue
                    self._unit_of_measurement = ctype['units']

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit_of_measurement

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return self._sensor_data
