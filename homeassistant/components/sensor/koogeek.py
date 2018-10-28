"""
Support for Homekit koogeek sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.koogeek/
"""
import logging

from homeassistant.components.homekit_controller import (HomeKitEntity,
                                                         KNOWN_ACCESSORIES)

from homeassistant.const import POWER_WATT_HOUR

DEPENDENCIES = ['homekit_controller']

KOOGEEK_CHARACTERISTICS = {
    '4aaaf931-0dec-11e5-b939-0800200c9a66': 'realtime_energy',
    '4aaaf932-0dec-11e5-b939-0800200c9a66': 'current_hour_data',
    '4aaaf93f-0dec-11e5-b939-0800200c9a66': 'running_time'
}

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up Homekit koogeek sensor support."""
    if discovery_info is not None:
        accessory = hass.data[KNOWN_ACCESSORIES][discovery_info['serial']]
        add_entities([KoogeekSensor(accessory, discovery_info)], True)


class KoogeekSensor(HomeKitEntity):
    """Representation of a Koogeek sensor."""

    def __init__(self, *args):
        """Initialise the sensor."""
        super().__init__(*args)
        self._sensor_data = {}
        self._state = None

    def update_characteristics(self, characteristics):
        """Synchronise the sensor state with Home Assistant."""

        for characteristic in characteristics:
            ctype = characteristic['type']
            ctype = KOOGEEK_CHARACTERISTICS.get(ctype, None)
            if ctype is not None:
                dataValue = characteristic['value']
                self._sensor_data[ctype] = dataValue
                if ctype == 'realtime_energy':
                    self._state = dataValue

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return POWER_WATT_HOUR

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return self._sensor_data
