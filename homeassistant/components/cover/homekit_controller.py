
"""
Support for Homekit Garage Covers.
For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/cover.homekit_controller/
"""
import logging

from homeassistant.components.homekit_controller import (
    HomeKitEntity, KNOWN_ACCESSORIES)
from homeassistant.components.cover import (
    CoverDevice, SUPPORT_OPEN, SUPPORT_CLOSE, SUPPORT_STOP)
from homeassistant.const import (
    STATE_UNKNOWN, STATE_CLOSED, STATE_OPEN, STATE_CLOSING, STATE_OPENING)
    
DEPENDENCIES = ['homekit_controller']

_LOGGER = logging.getLogger(__name__)

ATTR_DOOR_STATE = 'door_state'

STATE_STOPPED = 'stopped'

# Map of Homekit operation modes to hass modes
MODE_HOMEKIT_TO_HASS = {
    0: STATE_OPEN,
    1: STATE_CLOSED,
    2: STATE_OPENING,
    3: STATE_CLOSING,
    4: STATE_STOPPED,
}

# Map of hass operation modes to homekit modes
MODE_HASS_TO_HOMEKIT = {v: k for k, v in MODE_HOMEKIT_TO_HASS.items()}

def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up Homekit switch support."""
    if discovery_info is not None:
        accessory = hass.data[KNOWN_ACCESSORIES][discovery_info['serial']]
        add_entities([HomeKitCover(accessory, discovery_info)], True)


class HomeKitCover(HomeKitEntity, CoverDevice):
    """Representation of a Homekit cover."""

    def __init__(self, *args):
        """Initialise the cover."""
        super().__init__(*args)

        self._door_state_current = None
        self._door_state_target = None
        self._obstruction_detected = None
        self._name = None
        self._position_hold = None

    def update_characteristics(self, characteristics):
        """Synchronise the cover state with Home Assistant."""
        import homekit  # pylint: disable=import-error

        for characteristic in characteristics:
            ctype = characteristic['type']
            ctype = homekit.CharacteristicsTypes.get_short(ctype)

            if ctype == "door-state.current":
                self._chars['door-state.current'] = characteristic['iid']
                self._door_state_current = MODE_HOMEKIT_TO_HASS.get(characteristic['value'])
            elif ctype == "door-state.target":
                self._chars['door-state.target'] = characteristic['iid']
                self._door_state_target = MODE_HOMEKIT_TO_HASS.get(characteristic['value'])
            elif ctype == "obstruction-detected":
                self._chars['obstruction-detected'] = characteristic['iid']
                self._obstruction_detected = characteristic['value']
            elif ctype == "name":
                self._chars['name'] = characteristic['iid']
                self._name = characteristic['value']

    @property
    def is_closed(self):
        """Return if the cover is closed."""
        if self._door_state_current in [STATE_UNKNOWN]:
            return None
        return self._door_state_current in [STATE_CLOSED]
    
    @property
    def is_opening(self):
        """Return if the cover is opening or not."""
        return self._door_state_current in [STATE_OPENING]

    @property
    def is_closing(self):
        """Return if the cover is closing or not."""
        return self._door_state_current in [STATE_CLOSING]

    def close_cover(self, **kwargs):
        """Close the cover."""
        if self._door_state_current not in [STATE_CLOSED, STATE_CLOSING]:
            self._door_state_target = STATE_CLOSED
            self._door_state_current = STATE_CLOSING
            characteristics = [{'aid': self._aid,
                                'iid': self._chars['door-state.target'],
                                'value': MODE_HASS_TO_HOMEKIT[STATE_CLOSED]}]
            self.put_characteristics(characteristics)

    def open_cover(self, **kwargs):
        """Open the cover."""
        if self._door_state_current not in [STATE_OPEN, STATE_OPENING]:
            self._door_state_target = STATE_OPEN
            self._door_state_current = STATE_OPENING
            characteristics = [{'aid': self._aid,
                                'iid': self._chars['door-state.target'],
                                'value': MODE_HASS_TO_HOMEKIT[STATE_OPEN]}]
            self.put_characteristics(characteristics)

    def stop_cover(self, **kwargs):
        """Stop the cover."""
        if self._door_state_current not in [STATE_STOPPED, STATE_OPEN, STATE_CLOSED]:
            self._door_state_target = STATE_STOPPED
            self._door_state_current = STATE_STOPPED
            characteristics = [{'aid': self._aid,
                                'iid': self._chars['door-state.target'],
                                'value': MODE_HASS_TO_HOMEKIT[STATE_STOPPED]}]
            self.put_characteristics(characteristics)

    @property
    def name(self):
        """Return the name of the cover."""
        return self._name

    @property
    def available(self):
        """Return True if entity is available."""
        return self._door_state_current not in [STATE_UNKNOWN]

    @property
    def device_state_attributes(self):
        """Return the device state attributes."""
        data = {}

        if self._door_state_current is not None:
            data[ATTR_DOOR_STATE] = self._door_state_current

        return data

    @property
    def device_class(self):
        """Return the class of this device, from component DEVICE_CLASSES."""
        return 'garage'

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_OPEN | SUPPORT_CLOSE | SUPPORT_STOP