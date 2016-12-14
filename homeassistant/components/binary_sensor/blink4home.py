"""
Support for Blink4home cameras.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/blink4home/
"""
import logging
from homeassistant.components.binary_sensor import BinarySensorDevice

DEPENDENCIES = ['blink4home']
_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'Blink4Home'
ATTRIBUTION = 'Blink4Home camera support'

DOMAIN = 'blink4home'
DATA_BLINK = 'blink4home'


# pylint: disable=unused-argument
def setup_platform(hass, config, add_entities, discovery_info=None):
    """Setting up the sensor."""
    _LOGGER.debug('Setup blink4home sensor')
    blink = hass.data[DATA_BLINK]
    entity = Blink4HomeSensor(blink)

    add_entities([entity])
    _LOGGER.debug('Done setup blink4home')
    return blink.logged_in


class Blink4HomeSensor(BinarySensorDevice):
    """Blink4Home sensor."""

    def __init__(self, blink_instance):
        self._blink = blink_instance

    @property
    def name:
        """Return the namee of the sensor."""
        return 'Blink4Home Armed'

    @property
    def is_on(self):
        """Return the state of the sensor."""
        return self._blink.state

    def update(self):
        self._blink.update()
