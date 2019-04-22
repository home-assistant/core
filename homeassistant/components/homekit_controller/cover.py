"""Support for Homekit covers."""
import logging

from homeassistant.components.cover import (
    ATTR_POSITION, ATTR_TILT_POSITION, SUPPORT_CLOSE, SUPPORT_CLOSE_TILT,
    SUPPORT_OPEN, SUPPORT_OPEN_TILT, SUPPORT_SET_POSITION, SUPPORT_STOP,
    SUPPORT_SET_TILT_POSITION, CoverDevice)
from homeassistant.const import (
    STATE_CLOSED, STATE_CLOSING, STATE_OPEN, STATE_OPENING)

from . import KNOWN_DEVICES, HomeKitEntity

STATE_STOPPED = 'stopped'

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
    accessory = hass.data[KNOWN_DEVICES][discovery_info['serial']]

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
        self._state = None
        self._obstruction_detected = None
        self.lock_state = None

    @property
    def device_class(self):
        """Define this cover as a garage door."""
        return 'garage'

    def get_characteristic_types(self):
        """Define the homekit characteristics the entity cares about."""
        # pylint: disable=import-error
        from homekit.model.characteristics import CharacteristicsTypes
        return [
            CharacteristicsTypes.DOOR_STATE_CURRENT,
            CharacteristicsTypes.DOOR_STATE_TARGET,
            CharacteristicsTypes.OBSTRUCTION_DETECTED,
        ]

    def _update_door_state_current(self, value):
        self._state = CURRENT_GARAGE_STATE_MAP[value]

    def _update_obstruction_detected(self, value):
        self._obstruction_detected = value

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

    async def async_open_cover(self, **kwargs):
        """Send open command."""
        await self.set_door_state(STATE_OPEN)

    async def async_close_cover(self, **kwargs):
        """Send close command."""
        await self.set_door_state(STATE_CLOSED)

    async def set_door_state(self, state):
        """Send state command."""
        characteristics = [{'aid': self._aid,
                            'iid': self._chars['door-state.target'],
                            'value': TARGET_GARAGE_STATE_MAP[state]}]
        await self._accessory.put_characteristics(characteristics)

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
        self._state = None
        self._position = None
        self._tilt_position = None
        self._obstruction_detected = None
        self.lock_state = None
        self._features = (
            SUPPORT_OPEN | SUPPORT_CLOSE | SUPPORT_SET_POSITION)

    def get_characteristic_types(self):
        """Define the homekit characteristics the entity cares about."""
        # pylint: disable=import-error
        from homekit.model.characteristics import CharacteristicsTypes
        return [
            CharacteristicsTypes.POSITION_STATE,
            CharacteristicsTypes.POSITION_CURRENT,
            CharacteristicsTypes.POSITION_TARGET,
            CharacteristicsTypes.POSITION_HOLD,
            CharacteristicsTypes.VERTICAL_TILT_CURRENT,
            CharacteristicsTypes.VERTICAL_TILT_TARGET,
            CharacteristicsTypes.HORIZONTAL_TILT_CURRENT,
            CharacteristicsTypes.HORIZONTAL_TILT_TARGET,
            CharacteristicsTypes.OBSTRUCTION_DETECTED,
        ]

    def _setup_position_hold(self, char):
        self._features |= SUPPORT_STOP

    def _setup_vertical_tilt_current(self, char):
        self._features |= (
            SUPPORT_OPEN_TILT | SUPPORT_CLOSE_TILT |
            SUPPORT_SET_TILT_POSITION)

    def _setup_horizontal_tilt_current(self, char):
        self._features |= (
            SUPPORT_OPEN_TILT | SUPPORT_CLOSE_TILT |
            SUPPORT_SET_TILT_POSITION)

    def _update_position_state(self, value):
        self._state = CURRENT_WINDOW_STATE_MAP[value]

    def _update_position_current(self, value):
        self._position = value

    def _update_vertical_tilt_current(self, value):
        self._tilt_position = value

    def _update_horizontal_tilt_current(self, value):
        self._tilt_position = value

    def _update_obstruction_detected(self, value):
        self._obstruction_detected = value

    @property
    def supported_features(self):
        """Flag supported features."""
        return self._features

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

    async def async_stop_cover(self, **kwargs):
        """Send hold command."""
        characteristics = [{'aid': self._aid,
                            'iid': self._chars['position.hold'],
                            'value': 1}]
        await self._accessory.put_characteristics(characteristics)

    async def async_open_cover(self, **kwargs):
        """Send open command."""
        await self.async_set_cover_position(position=100)

    async def async_close_cover(self, **kwargs):
        """Send close command."""
        await self.async_set_cover_position(position=0)

    async def async_set_cover_position(self, **kwargs):
        """Send position command."""
        position = kwargs[ATTR_POSITION]
        characteristics = [{'aid': self._aid,
                            'iid': self._chars['position.target'],
                            'value': position}]
        await self._accessory.put_characteristics(characteristics)

    @property
    def current_cover_tilt_position(self):
        """Return current position of cover tilt."""
        return self._tilt_position

    async def async_set_cover_tilt_position(self, **kwargs):
        """Move the cover tilt to a specific position."""
        tilt_position = kwargs[ATTR_TILT_POSITION]
        if 'vertical-tilt.target' in self._chars:
            characteristics = [{'aid': self._aid,
                                'iid': self._chars['vertical-tilt.target'],
                                'value': tilt_position}]
            await self._accessory.put_characteristics(characteristics)
        elif 'horizontal-tilt.target' in self._chars:
            characteristics = [{'aid': self._aid,
                                'iid':
                                self._chars['horizontal-tilt.target'],
                                'value': tilt_position}]
            await self._accessory.put_characteristics(characteristics)

    @property
    def device_state_attributes(self):
        """Return the optional state attributes."""
        state_attributes = {}
        if self._obstruction_detected is not None:
            state_attributes['obstruction-detected'] = \
                self._obstruction_detected

        return state_attributes
