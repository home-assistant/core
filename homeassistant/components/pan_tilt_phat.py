"""
Support for pan-tilt pHAT.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/pan_tilt_phat
"""


import logging

from homeassistant.helpers.entity import Entity

REQUIREMENTS = ['pantilthat==0.0.4']
_LOGGER = logging.getLogger(__name__)
DOMAIN = 'pan_tilt_phat'


def setup(hass, config):
    """Set up the pan-tilt-hat component."""
    _LOGGER.info("Creating new pan-tilt-hat component")

    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = []
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
    hass.data[DOMAIN] = PanTiltPhat(pantilthat)
    return True


class PanTiltPhat(Entity):
    """Representation of the stage."""

    ICON = 'mdi:camera-switch'

    def __init__(self, pantilthat):
        """Initialise the stage."""
        self._name = DOMAIN
        self._pantilthat = pantilthat
        self._pan = self._pantilthat.get_pan()
        self._tilt = self._pantilthat.get_tilt()

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return self.ICON

    def update(self):
        """Get the latest data from the stage."""
        self._pan = self._pantilthat.get_pan()
        self._tilt = self._pantilthat.get_tilt()
