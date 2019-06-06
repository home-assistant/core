"""Support for toggling Amcrest IP camera settings."""
import logging

from homeassistant.const import CONF_NAME, CONF_SWITCHES
from homeassistant.helpers.entity import ToggleEntity

from .const import DATA_AMCREST

_LOGGER = logging.getLogger(__name__)

# Switch types are defined like: Name, icon
SWITCHES = {
    'motion_detection': ['Motion Detection', 'mdi:run-fast'],
    'motion_recording': ['Motion Recording', 'mdi:record-rec']
}


async def async_setup_platform(
        hass, config, async_add_entities, discovery_info=None):
    """Set up the IP Amcrest camera switch platform."""
    if discovery_info is None:
        return

    name = discovery_info[CONF_NAME]
    device = hass.data[DATA_AMCREST]['devices'][name]
    async_add_entities(
        [AmcrestSwitch(name, device, setting)
         for setting in discovery_info[CONF_SWITCHES]],
        True)


class AmcrestSwitch(ToggleEntity):
    """Representation of an Amcrest IP camera switch."""

    def __init__(self, name, device, setting):
        """Initialize the Amcrest switch."""
        self._name = '{} {}'.format(name, SWITCHES[setting][0])
        self._api = device.api
        self._setting = setting
        self._state = False
        self._icon = SWITCHES[setting][1]

    @property
    def name(self):
        """Return the name of the switch if any."""
        return self._name

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self._state

    def turn_on(self, **kwargs):
        """Turn setting on."""
        if self._setting == 'motion_detection':
            self._api.motion_detection = 'true'
        elif self._setting == 'motion_recording':
            self._api.motion_recording = 'true'

    def turn_off(self, **kwargs):
        """Turn setting off."""
        if self._setting == 'motion_detection':
            self._api.motion_detection = 'false'
        elif self._setting == 'motion_recording':
            self._api.motion_recording = 'false'

    def update(self):
        """Update setting state."""
        _LOGGER.debug("Polling state for setting: %s ", self._name)

        if self._setting == 'motion_detection':
            detection = self._api.is_motion_detector_on()
        elif self._setting == 'motion_recording':
            detection = self._api.is_record_on_motion_detection()

        self._state = detection

    @property
    def icon(self):
        """Return the icon for the switch."""
        return self._icon
