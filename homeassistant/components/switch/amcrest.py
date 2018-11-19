"""
Support for toggling Amcrest IP camera settings.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.amcrest/
"""
import logging

from homeassistant.components.amcrest import DATA_AMCREST, SWITCHES
from homeassistant.const import (
    CONF_NAME, CONF_SWITCHES, STATE_OFF, STATE_ON)
from homeassistant.helpers.entity import ToggleEntity

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['amcrest']


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up the IP Amcrest camera switch platform."""
    if discovery_info is None:
        return

    name = discovery_info[CONF_NAME]
    switches = discovery_info[CONF_SWITCHES]
    camera = hass.data[DATA_AMCREST][name].device

    all_switches = []

    for setting in switches:
        all_switches.append(AmcrestSwitch(setting, camera, name))

    async_add_entities(all_switches, True)


class AmcrestSwitch(ToggleEntity):
    """Representation of an Amcrest IP camera switch."""

    def __init__(self, setting, camera, name):
        """Initialize the Amcrest switch."""
        self._setting = setting
        self._camera = camera
        self._name = '{} {}'.format(SWITCHES[setting][0], name)
        self._icon = SWITCHES[setting][1]
        self._state = None

    @property
    def name(self):
        """Return the name of the switch if any."""
        return self._name

    @property
    def state(self):
        """Return the state of the switch."""
        return self._state

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self._state == STATE_ON

    def turn_on(self, **kwargs):
        """Turn setting on."""
        if self._setting == 'motion_detection':
            self._camera.motion_detection = 'true'
        elif self._setting == 'motion_recording':
            self._camera.motion_recording = 'true'

    def turn_off(self, **kwargs):
        """Turn setting off."""
        if self._setting == 'motion_detection':
            self._camera.motion_detection = 'false'
        elif self._setting == 'motion_recording':
            self._camera.motion_recording = 'false'

    def update(self):
        """Update setting state."""
        _LOGGER.debug("Polling state for setting: %s ", self._name)

        if self._setting == 'motion_detection':
            detection = self._camera.is_motion_detector_on()
        elif self._setting == 'motion_recording':
            detection = self._camera.is_record_on_motion_detection()

        self._state = STATE_ON if detection else STATE_OFF

    @property
    def icon(self):
        """Return the icon for the switch."""
        return self._icon
