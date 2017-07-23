"""
Support for Roomba Vaccums switches.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.roomba/
"""
import logging
from homeassistant.const import (STATE_OFF, STATE_ON)
from homeassistant.helpers.entity import ToggleEntity
from homeassistant.components.roomba import ROOMBA_ROBOTS

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['roomba']

SWITCH_TYPE_CLEAN = 'clean'

SWITCH_TYPES = {
    SWITCH_TYPE_CLEAN: ['Clean']
}


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Roomba switches."""
    dev = []
    for roomba_hub in hass.data[ROOMBA_ROBOTS]:
        for type_name in SWITCH_TYPES:
            dev.append(RoombaSwitch(hass, roomba_hub, type_name))
    _LOGGER.debug('Adding switches %s', dev)
    add_devices(dev)


class RoombaSwitch(ToggleEntity):
    """Roomba Switches."""

    def __init__(self, hass, roomba_hub, switch_type):
        """Initialize the Roomba switches."""
        self.roomba_hub = roomba_hub
        self._state = None
        self.switch_type = switch_type
        if self.switch_type == SWITCH_TYPE_CLEAN:
            self._switch_name = 'Roomba Mission'
        self.__set_switch_state_from_hub()

    def __set_switch_state_from_hub(self):
        roomba_data = self.roomba_hub._data
        roomba_name = roomba_data['state'].get('name', 'Roomba')
        if self.switch_type == SWITCH_TYPE_CLEAN:
            self._state = roomba_data['status'] == 'run'
            _LOGGER.debug('Set roomba mission switch to %s', self._state)
            self._switch_name = '{} Mission'.format(roomba_name)
        _LOGGER.debug('Switch state: %s', self._state)

    def update(self):
        """Update the states of Roomba switches."""
        _LOGGER.debug("Running switch update")
        self.roomba_hub.update()
        self.__set_switch_state_from_hub()

    @property
    def name(self):
        """Return the name of the switch."""
        return self._switch_name

    @property
    def available(self):
        """Return True if entity is available."""
        return self._state is not None

    @property
    def is_on(self):
        """Return true if switch is on."""
        # TODO
        return False

    def turn_on(self, **kwargs):
        """Turn the switch on."""
        if self.switch_type == SWITCH_TYPE_CLEAN:
            self.roomba_hub.send_command('clean')

    def turn_off(self, **kwargs):
        """Turn the switch off."""
        if self.switch_type == SWITCH_TYPE_CLEAN:
            self.roomba_hub.send_command('dock')
