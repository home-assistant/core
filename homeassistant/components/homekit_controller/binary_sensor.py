"""Support for Homekit motion sensors."""
import logging

from homeassistant.components.binary_sensor import BinarySensorDevice

from . import KNOWN_DEVICES, HomeKitEntity

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up Homekit motion sensor support."""
    if discovery_info is not None:
        accessory = hass.data[KNOWN_DEVICES][discovery_info['serial']]
        add_entities([HomeKitMotionSensor(accessory, discovery_info)], True)


class HomeKitMotionSensor(HomeKitEntity, BinarySensorDevice):
    """Representation of a Homekit sensor."""

    def __init__(self, *args):
        """Initialise the entity."""
        super().__init__(*args)
        self._on = False

    def get_characteristic_types(self):
        """Define the homekit characteristics the entity is tracking."""
        # pylint: disable=import-error
        from homekit.model.characteristics import CharacteristicsTypes

        return [
            CharacteristicsTypes.MOTION_DETECTED,
        ]

    def _update_motion_detected(self, value):
        self._on = value

    @property
    def device_class(self):
        """Define this binary_sensor as a motion sensor."""
        return 'motion'

    @property
    def is_on(self):
        """Has motion been detected."""
        return self._on
