"""
Support for Homekit Cover.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/cover.homekit_controller/
"""
import logging

from homeassistant.components.homekit_controller import (HomeKitEntity,
                                                         KNOWN_ACCESSORIES)
from homeassistant.components.cover import (
    CoverDevice, SUPPORT_OPEN, SUPPORT_CLOSE, SUPPORT_SET_POSITION,
    SUPPORT_OPEN_TILT, SUPPORT_CLOSE_TILT, SUPPORT_SET_TILT_POSITION,
    ATTR_POSITION, ATTR_TILT_POSITION)
from homeassistant.const import (
    STATE_CLOSED, STATE_CLOSING, STATE_OPEN, STATE_OPENING)

STATE_STOPPED = 'stopped'

DEPENDENCIES = ['homekit_controller']

_LOGGER = logging.getLogger(__name__)

CURRENT_GARAGE_STATE_MAP = {
    0: STATE_OPEN,
    1: STATE_CLOSED,
    2: STATE_OPENING,
    3: STATE_CLOSING,
    4: STATE_STOPPED
}

TARGET_GARAGE_STATE_MAP = {
    STATE_OPEN: 0,
    STATE_CLOSED: 1,
    STATE_STOPPED: 2
}

CURRENT_WINDOW_STATE_MAP = {
    0: STATE_OPENING,
    1: STATE_CLOSING,
    2: STATE_STOPPED
}


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up HomeKit Cover support."""
    if discovery_info is None:
        return
    accessory = hass.data[KNOWN_ACCESSORIES][discovery_info['serial']]

    if discovery_info['device-type'] == 'garage-door-opener':
        add_entities([HomeKitGarageDoorCover(accessory, discovery_info)],
                     True)
    else:
        add_entities([HomeKitWindowCover(accessory, discovery_info)],
                     True)


class HomeKitGarageDoorCover(HomeKitEntity, CoverDevice):
    """Representation of a HomeKit Garage Door."""

    def __init__(self, accessory, discovery_info):
        """Initialise the Cover."""
        super().__init__(accessory, discovery_info)
        self._name = None
        self._state = None
        self._obstruction_detected = None
        self.lock_state = None

    @property
    def device_class(self):
        """Define this cover as a garage door."""
        return 'garage'

    def update_characteristics(self, characteristics):
        """Synchronise the Cover state with Home Assistant."""
        # pylint: disable=import-error
        from homekit.model.characteristics import CharacteristicsTypes

        for characteristic in characteristics:
            ctype = characteristic['type']
            ctype = CharacteristicsTypes.get_short(ctype)
            if ctype == "door-state.current":
                self._chars['door-state.current'] = \
                    characteristic['iid']
                self._state = CURRENT_GARAGE_STATE_MAP[characteristic['value']]
            elif ctype == "door-state.target":
                self._chars['door-state.target'] = \
                    characteristic['iid']
            elif ctype == "obstruction-detected":
                self._chars['obstruction-detected'] = characteristic['iid']
                self._obstruction_detected = characteristic['value']
            elif ctype == "name":
                self._chars['name'] = characteristic['iid']
                self._name = characteristic['value']

    @property
    def name(self):
        """Return the name of the cover."""
        return self._name

    @property
    def available(self):
        """Return True if entity is available."""
        return self._state is not None

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_OPEN | SUPPORT_CLOSE

    @property
    def is_closed(self):
        """Return true if cover is closed, else False."""
        return self._state == STATE_CLOSED

    @property
    def is_closing(self):
        """Return if the cover is closing or not."""
        return self._state == STATE_CLOSING

    @property
    def is_opening(self):
        """Return if the cover is opening or not."""
        return self._state == STATE_OPENING

    def open_cover(self, **kwargs):
        """Send open command."""
        self.set_door_state(STATE_OPEN)

    def close_cover(self, **kwargs):
        """Send close command."""
        self.set_door_state(STATE_CLOSED)

    def set_door_state(self, state):
        """Send state command."""
        characteristics = [{'aid': self._aid,
                            'iid': self._chars['door-state.target'],
                            'value': TARGET_GARAGE_STATE_MAP[state]}]
        self.put_characteristics(characteristics)

    @property
    def device_state_attributes(self):
        """Return the optional state attributes."""
        if self._obstruction_detected is None:
            return None

        return {
            'obstruction-detected': self._obstruction_detected,
        }


class HomeKitWindowCover(HomeKitEntity, CoverDevice):
    """Representation of a HomeKit Window or Window Covering."""

    def __init__(self, accessory, discovery_info):
        """Initialise the Cover."""
        super().__init__(accessory, discovery_info)
        self._name = None
        self._state = None
        self._position = None
        self._tilt_position = None
        self._hold = None
        self._obstruction_detected = None
        self.lock_state = None

    @property
    def available(self):
        """Return True if entity is available."""
        return self._state is not None

    def update_characteristics(self, characteristics):
        """Synchronise the Cover state with Home Assistant."""
        # pylint: disable=import-error
        from homekit.model.characteristics import CharacteristicsTypes

        for characteristic in characteristics:
            ctype = characteristic['type']
            ctype = CharacteristicsTypes.get_short(ctype)
            if ctype == "position.state":
                self._chars['position.state'] = \
                    characteristic['iid']
                if 'value' in characteristic:
                    self._state = \
                        CURRENT_WINDOW_STATE_MAP[characteristic['value']]
            elif ctype == "position.current":
                self._chars['position.current'] = \
                    characteristic['iid']
                self._position = characteristic['value']
            elif ctype == "position.target":
                self._chars['position.target'] = \
                    characteristic['iid']
            elif ctype == "position.hold":
                self._chars['position.hold'] = characteristic['iid']
                if 'value' in characteristic:
                    self._hold = characteristic['value']
            elif ctype == "vertical-tilt.current":
                self._chars['vertical-tilt.current'] = characteristic['iid']
                if characteristic['value'] is not None:
                    self._tilt_position = characteristic['value']
            elif ctype == "horizontal-tilt.current":
                self._chars['horizontal-tilt.current'] = characteristic['iid']
                if characteristic['value'] is not None:
                    self._tilt_position = characteristic['value']
            elif ctype == "vertical-tilt.target":
                self._chars['vertical-tilt.target'] = \
                    characteristic['iid']
            elif ctype == "horizontal-tilt.target":
                self._chars['vertical-tilt.target'] = \
                    characteristic['iid']
            elif ctype == "obstruction-detected":
                self._chars['obstruction-detected'] = characteristic['iid']
                self._obstruction_detected = characteristic['value']
            elif ctype == "name":
                self._chars['name'] = characteristic['iid']
                if 'value' in characteristic:
                    self._name = characteristic['value']

    @property
    def name(self):
        """Return the name of the cover."""
        return self._name

    @property
    def supported_features(self):
        """Flag supported features."""
        supported_features = (
            SUPPORT_OPEN | SUPPORT_CLOSE | SUPPORT_SET_POSITION)

        if self._tilt_position is not None:
            supported_features |= (
                SUPPORT_OPEN_TILT | SUPPORT_CLOSE_TILT |
                SUPPORT_SET_TILT_POSITION)

        return supported_features

    @property
    def current_cover_position(self):
        """Return the current position of cover."""
        return self._position

    @property
    def is_closed(self):
        """Return true if cover is closed, else False."""
        return self._position == 0

    @property
    def is_closing(self):
        """Return if the cover is closing or not."""
        return self._state == STATE_CLOSING

    @property
    def is_opening(self):
        """Return if the cover is opening or not."""
        return self._state == STATE_OPENING

    def open_cover(self, **kwargs):
        """Send open command."""
        self.set_cover_position(position=100)

    def close_cover(self, **kwargs):
        """Send close command."""
        self.set_cover_position(position=0)

    def set_cover_position(self, **kwargs):
        """Send position command."""
        position = kwargs[ATTR_POSITION]
        characteristics = [{'aid': self._aid,
                            'iid': self._chars['position.target'],
                            'value': position}]
        self.put_characteristics(characteristics)

    @property
    def current_cover_tilt_position(self):
        """Return current position of cover tilt."""
        return self._tilt_position

    def set_cover_tilt_position(self, **kwargs):
        """Move the cover tilt to a specific position."""
        tilt_position = kwargs[ATTR_TILT_POSITION]
        if 'vertical-tilt.target' in self._chars:
            characteristics = [{'aid': self._aid,
                                'iid': self._chars['vertical-tilt.target'],
                                'value': tilt_position}]
            self.put_characteristics(characteristics)
        elif 'horizontal-tilt.target' in self._chars:
            characteristics = [{'aid': self._aid,
                                'iid':
                                self._chars['horizontal-tilt.target'],
                                'value': tilt_position}]
            self.put_characteristics(characteristics)

    @property
    def device_state_attributes(self):
        """Return the optional state attributes."""
        state_attributes = {}
        if self._obstruction_detected is not None:
            state_attributes['obstruction-detected'] = \
                self._obstruction_detected

        if self._hold is not None:
            state_attributes['hold-position'] = \
                self._hold

        return state_attributes
