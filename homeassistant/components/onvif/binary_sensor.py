"""Support for ONVIF Cameras as motion sensors."""
import logging

from homeassistant.components.binary_sensor import BinarySensorDevice
from . import ONVIFHassCamera, DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up ONVIF motion sensor support."""
    if discovery_info is not None:
        camera = hass.data[DOMAIN][discovery_info['serial']]

        supports_motion_detection = camera.supports_motion_detection
        if supports_motion_detection:
            _LOGGER.info("Camera '%s' supports motion detection, "
                         "adding as binary sensor", camera.name)

            await async_add_entities(
                [ONVIFMotionSensor(camera, discovery_info)], True)

class ONVIFMotionSensor(ONVIFHassCamera, BinarySensorDevice):
    """Representation of a ONVIF sensor."""

    def __init__(self, *args):
        """Initialise the entity."""
        super().__init__(*args)
        self._on = False

    # def get_characteristic_types(self):
    #     """Define the ONVIF characteristics the entity is tracking."""
    #     # pylint: disable=import-error
    #     from homekit.model.characteristics import CharacteristicsTypes

    #     return [
    #         CharacteristicsTypes.MOTION_DETECTED,
    #     ]

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