"""
Support for Tahoma cover - shutters etc.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/cover.tahoma/
"""
import logging

from homeassistant.components.cover import CoverDevice, ATTR_POSITION
from homeassistant.components.tahoma import (
    DOMAIN as TAHOMA_DOMAIN, TahomaDevice)

DEPENDENCIES = ['tahoma']

_LOGGER = logging.getLogger(__name__)

ATTR_CLOSURE = 'closure'
ATTR_MEM_POS = 'memorized_position'
ATTR_RSSI_LEVEL = 'rssi_level'
ATTR_OPEN_CLOSE = 'open_close'
ATTR_STATUS = 'status'
ATTR_LOCK_TIMER = 'priority_lock_timer'
ATTR_LOCK_LEVEL = 'priority_lock_level'
ATTR_LOCK_ORIG = 'priority_lock_originator'


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Tahoma covers."""
    controller = hass.data[TAHOMA_DOMAIN]['controller']
    devices = []
    for device in hass.data[TAHOMA_DOMAIN]['devices']['cover']:
        devices.append(TahomaCover(device, controller))
    add_devices(devices, True)


class TahomaCover(TahomaDevice, CoverDevice):
    """Representation a Tahoma Cover."""

    def __init__(self, tahoma_device, controller):
        """Initialize the device."""
        super().__init__(tahoma_device, controller)

        self._closure = 0
        # 100 equals open
        self._position = 100
        self._closed = False
        self._icon = None
        # Can be 0 and bigger
        self._lock_timer = 0
        # Can be 'comfortLevel1'
        self._lock_level = None
        # Can be 'wind'
        self._lock_originator = None

    def update(self):
        """Update method."""
        self.controller.get_states([self.tahoma_device])

        if 'core:ClosureState' in self.tahoma_device.active_states:
            self._closure = \
                self.tahoma_device.active_states['core:ClosureState']
        else:
            self._closure = None
        if 'core:PriorityLockTimerState' in self.tahoma_device.active_states:
            self._lock_timer = \
                self.tahoma_device.active_states['core:PriorityLockTimerState']
        else:
            self._lock_timer = None
        if 'io:PriorityLockLevelState' in self.tahoma_device.active_states:
            self._lock_level = \
                self.tahoma_device.active_states['io:PriorityLockLevelState']
        else:
            self._lock_level = None
        if 'io:PriorityLockOriginatorState' in \
                self.tahoma_device.active_states:
            self._lock_originator = \
                self.tahoma_device.active_states[
                    'io:PriorityLockOriginatorState']
        else:
            self._lock_originator = None

        # Define which icon to use
        if self._lock_timer > 0:
            if self._lock_originator == 'wind':
                self._icon = 'mdi:weather-windy'
            else:
                self._icon = 'mdi:lock-alert'
        else:
            self._icon = None

        # Define current position.
        #   _position: 0 is closed, 100 is fully open.
        #   'core:ClosureState': 100 is closed, 0 is fully open.
        if 'core:ClosureState' in self.tahoma_device.active_states:
            self._position = 100 - \
                self.tahoma_device.active_states['core:ClosureState']
            if self._position <= 5:
                self._position = 0
            if self._position >= 95:
                self._position = 100
            self._closed = self._position == 0
        else:
            self._position = None
            if 'core:OpenClosedState' in self.tahoma_device.active_states:
                self._closed = \
                    self.tahoma_device.active_states['core:OpenClosedState']\
                    == 'closed'
            else:
                self._closed = False

        _LOGGER.debug("Update %s, position: %d", self._name, self._position)

    @property
    def current_cover_position(self):
        """Return current position of cover."""
        return self._position

    def set_cover_position(self, **kwargs):
        """Move the cover to a specific position."""
        self.apply_action('setPosition', 100 - kwargs.get(ATTR_POSITION))

    @property
    def is_closed(self):
        """Return if the cover is closed."""
        return self._closed

    @property
    def device_class(self):
        """Return the class of the device."""
        if self.tahoma_device.type == 'io:WindowOpenerVeluxIOComponent':
            return 'window'
        return None

    @property
    def device_state_attributes(self):
        """Return the device state attributes."""
        attr = {}
        super_attr = super().device_state_attributes
        if super_attr is not None:
            attr.update(super_attr)

        if self._closure is not None:
            attr[ATTR_CLOSURE] = self._closure
        if 'core:Memorized1PositionState' in self.tahoma_device.active_states:
            attr[ATTR_MEM_POS] = self.tahoma_device.active_states[
                'core:Memorized1PositionState']
        if 'core:RSSILevelState' in self.tahoma_device.active_states:
            attr[ATTR_RSSI_LEVEL] = self.tahoma_device.active_states[
                'core:RSSILevelState']
        if 'core:OpenClosedState' in self.tahoma_device.active_states:
            attr[ATTR_OPEN_CLOSE] = self.tahoma_device.active_states[
                'core:OpenClosedState']
        if 'core:StatusState' in self.tahoma_device.active_states:
            attr[ATTR_STATUS] = self.tahoma_device.active_states[
                'core:StatusState']
        if self._lock_timer is not None:
            attr[ATTR_LOCK_TIMER] = self._lock_timer
        if self._lock_level is not None:
            attr[ATTR_LOCK_LEVEL] = self._lock_level
        if self._lock_originator is not None:
            attr[ATTR_LOCK_ORIG] = self._lock_originator
        return attr

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        return self._icon

    def open_cover(self, **kwargs):
        """Open the cover."""
        if self.tahoma_device.type == 'io:HorizontalAwningIOComponent':
            # The commands open and close seem to be reversed.
            self.apply_action('close')
        else:
            self.apply_action('open')

    def close_cover(self, **kwargs):
        """Close the cover."""
        if self.tahoma_device.type == 'io:HorizontalAwningIOComponent':
            # The commands open and close seem to be reversed.
            self.apply_action('open')
        else:
            self.apply_action('close')

    def stop_cover(self, **kwargs):
        """Stop the cover."""
        if self.tahoma_device.type == \
           'io:RollerShutterWithLowSpeedManagementIOComponent':
            self.apply_action('setPosition', 'secured')
        elif self.tahoma_device.type in \
                ('rts:BlindRTSComponent',
                 'io:ExteriorVenetianBlindIOComponent'):
            self.apply_action('my')
        elif self.tahoma_device.type in \
                ('io:VerticalExteriorAwningIOComponent',
                 'io:HorizontalAwningIOComponent'):
            self.apply_action('stop')
        else:
            self.apply_action('stopIdentify')
