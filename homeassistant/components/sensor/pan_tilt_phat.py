"""
Support for pan-tilt pHAT.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/sensor.pan_tilt_phat
"""

from datetime import timedelta
import logging

from homeassistant.helpers.entity import Entity

REQUIREMENTS = ['pantilthat==0.0.4']
_LOGGER = logging.getLogger(__name__)
DOMAIN = 'pan_tilt_phat'
SCAN_INTERVAL = timedelta(seconds=1)

def setup_platform(hass, config, add_devices, discovery_info=None):
    try:
        import pantilthat
    except OSError:
        _LOGGER.error("No pan-tilt pHAT was found.")
        return False

    def home_service(call):
        """Return the stage to home."""
        pantilthat.pan(0)
        pantilthat.tilt(0)
        return True

    def pan_service(call):
        """Pan the stage."""
        pantilthat.pan(call.data.get("Pan"))
        return True

    def tilt_service(call):
        """Pan the stage."""
        pantilthat.tilt(call.data.get("Tilt"))
        return True

    hass.services.register(DOMAIN, 'home', home_service)
    hass.services.register(DOMAIN, 'tilt', tilt_service)
    hass.services.register(DOMAIN, 'pan', pan_service)
    add_devices([PanTiltPhat(pantilthat)], True)
    return True


class PanTiltPhat(Entity):
    """Representation of the stage."""

    ICON = 'mdi:camera-switch'

    def __init__(self, pantilthat):
        """Initialize the stage."""
        self._name = DOMAIN
        self._state = None       # json obj with pan and tilt
        self._pantilthat = pantilthat

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return self.ICON

    def update(self):
        """Get the latest data from the stage.
        Issue with tilt"""
        self._pan = self._pantilthat.get_pan()
        self._tilt = self._pantilthat.get_tilt()
        self._state = "Pan:{}".format(self._pan)
