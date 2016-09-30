"""
Support for Harmony device current activity as a sensor.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/harmony/
"""

import logging
import homeassistant.components.harmony as harmony
from homeassistant.helpers.entity import Entity
from homeassistant.const import CONF_NAME, CONF_USERNAME, CONF_PASSWORD, CONF_PORT

DEPENDENCIES = ['harmony']
_LOGGER = logging.getLogger(__name__)
CONF_IP = 'ip'


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the sensor platform."""

    for hub in harmony.HUB_CONF_GLOBAL:
        add_devices([HarmonySensor(hub[CONF_NAME],
                                   hub[CONF_USERNAME],
                                   hub[CONF_PASSWORD],
                                   hub[CONF_IP],
                                   hub[CONF_PORT])])
    return True



class HarmonySensor(harmony.HarmonyDevice):
    """Representation of a Harmony Sensor."""
    def __init__(self, name, username, password, ip, port):
        super().__init__(name, username, password, ip, port)
        self._name = 'harmony_' + self._name
   





