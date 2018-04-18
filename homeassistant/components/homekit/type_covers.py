"""Class to hold all cover accessories."""
import logging

from homeassistant.components.cover import (
    ATTR_CURRENT_POSITION, ATTR_POSITION, DOMAIN, SUPPORT_STOP)
from homeassistant.const import (
    ATTR_ENTITY_ID, SERVICE_SET_COVER_POSITION, STATE_OPEN, STATE_CLOSED,
    SERVICE_OPEN_COVER, SERVICE_CLOSE_COVER, SERVICE_STOP_COVER,
    ATTR_SUPPORTED_FEATURES)

from . import TYPES
from .accessories import HomeAccessory, add_preload_service, setup_char
from .const import (
    CATEGORY_WINDOW_COVERING, SERV_WINDOW_COVERING,
    CHAR_CURRENT_POSITION, CHAR_TARGET_POSITION, CHAR_POSITION_STATE,
    CATEGORY_GARAGE_DOOR_OPENER, SERV_GARAGE_DOOR_OPENER,
    CHAR_CURRENT_DOOR_STATE, CHAR_TARGET_DOOR_STATE)

_LOGGER = logging.getLogger(__name__)


@TYPES.register('GarageDoorOpener')
class GarageDoorOpener(HomeAccessory):
    """Generate a Garage Door Opener accessory for a cover entity.

    The cover entity must be in the 'garage' device class
    and support no more than open, close, and stop.
    """

    def __init__(self, *args, config):
        """Initialize a GarageDoorOpener accessory object."""
        super().__init__(*args, category=CATEGORY_GARAGE_DOOR_OPENER)
        self.flag_target_state = False

        serv_garage_door = add_preload_service(self, SERV_GARAGE_DOOR_OPENER)
        self.char_current_state = setup_char(
            CHAR_CURRENT_DOOR_STATE, serv_garage_door, value=0)
        self.char_target_state = setup_char(
            CHAR_TARGET_DOOR_STATE, serv_garage_door, value=0,
            callback=self.set_state)

    def set_state(self, value):
        """Change garage state if call came from HomeKit."""
        _LOGGER.debug('%s: Set state to %d', self.entity_id, value)
        self.flag_target_state = True

        if value == 0:
            self.char_current_state.set_value(3)
            self.hass.components.cover.open_cover(self.entity_id)
        elif value == 1:
            self.char_current_state.set_value(2)
            self.hass.components.cover.close_cover(self.entity_id)

    def update_state(self, new_state):
        """Update cover state after state changed."""
        hass_state = new_state.state
        if hass_state in (STATE_OPEN, STATE_CLOSED):
            current_state = 0 if hass_state == STATE_OPEN else 1
            self.char_current_state.set_value(current_state)
            if not self.flag_target_state:
                self.char_target_state.set_value(current_state)
            self.flag_target_state = False


@TYPES.register('WindowCovering')
class WindowCovering(HomeAccessory):
    """Generate a Window accessory for a cover entity.

    The cover entity must support: set_cover_position.
    """

    def __init__(self, *args, config):
        """Initialize a WindowCovering accessory object."""
        super().__init__(*args, category=CATEGORY_WINDOW_COVERING)
        self.homekit_target = None

        serv_cover = add_preload_service(self, SERV_WINDOW_COVERING)
        self.char_current_position = setup_char(
            CHAR_CURRENT_POSITION, serv_cover, value=0)
        self.char_target_position = setup_char(
            CHAR_TARGET_POSITION, serv_cover, value=0,
            callback=self.move_cover)

    def move_cover(self, value):
        """Move cover to value if call came from HomeKit."""
        _LOGGER.debug('%s: Set position to %d', self.entity_id, value)
        self.homekit_target = value

        params = {ATTR_ENTITY_ID: self.entity_id, ATTR_POSITION: value}
        self.hass.services.call(DOMAIN, SERVICE_SET_COVER_POSITION, params)

    def update_state(self, new_state):
        """Update cover position after state changed."""
        current_position = new_state.attributes.get(ATTR_CURRENT_POSITION)
        if isinstance(current_position, int):
            self.char_current_position.set_value(current_position)
            if self.homekit_target is None or \
                    abs(current_position - self.homekit_target) < 6:
                self.char_target_position.set_value(current_position)
                self.homekit_target = None


@TYPES.register('WindowCoveringBasic')
class WindowCoveringBasic(HomeAccessory):
    """Generate a Window accessory for a cover entity.

    The cover entity must support: open_cover, close_cover,
    stop_cover (optional).
    """

    def __init__(self, *args, config):
        """Initialize a WindowCovering accessory object."""
        super().__init__(*args, category=CATEGORY_WINDOW_COVERING)
        features = self.hass.states.get(self.entity_id) \
            .attributes.get(ATTR_SUPPORTED_FEATURES)
        self.supports_stop = features & SUPPORT_STOP

        serv_cover = add_preload_service(self, SERV_WINDOW_COVERING)
        self.char_current_position = setup_char(
            CHAR_CURRENT_POSITION, serv_cover, value=0)
        self.char_target_position = setup_char(
            CHAR_TARGET_POSITION, serv_cover, value=0,
            callback=self.move_cover)
        self.char_position_state = setup_char(
            CHAR_POSITION_STATE, serv_cover, value=2)

    def move_cover(self, value):
        """Move cover to value if call came from HomeKit."""
        _LOGGER.debug('%s: Set position to %d', self.entity_id, value)

        if self.supports_stop:
            if value > 70:
                service, position = (SERVICE_OPEN_COVER, 100)
            elif value < 30:
                service, position = (SERVICE_CLOSE_COVER, 0)
            else:
                service, position = (SERVICE_STOP_COVER, 50)
        else:
            if value >= 50:
                service, position = (SERVICE_OPEN_COVER, 100)
            else:
                service, position = (SERVICE_CLOSE_COVER, 0)

        self.hass.services.call(DOMAIN, service,
                                {ATTR_ENTITY_ID: self.entity_id})

        # Snap the current/target position to the expected final position.
        self.char_current_position.set_value(position)
        self.char_target_position.set_value(position)
        self.char_position_state.set_value(2)

    def update_state(self, new_state):
        """Update cover position after state changed."""
        position_mapping = {STATE_OPEN: 100, STATE_CLOSED: 0}
        hk_position = position_mapping.get(new_state.state)
        if hk_position is not None:
            self.char_current_position.set_value(hk_position)
            self.char_target_position.set_value(hk_position)
            self.char_position_state.set_value(2)
