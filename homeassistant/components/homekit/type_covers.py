"""Class to hold all cover accessories."""
import logging

from pyhap.const import CATEGORY_GARAGE_DOOR_OPENER, CATEGORY_WINDOW_COVERING

from homeassistant.components.cover import (
    ATTR_CURRENT_POSITION,
    ATTR_CURRENT_TILT_POSITION,
    ATTR_POSITION,
    ATTR_TILT_POSITION,
    DOMAIN,
    SUPPORT_SET_TILT_POSITION,
    SUPPORT_STOP,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    SERVICE_CLOSE_COVER,
    SERVICE_OPEN_COVER,
    SERVICE_SET_COVER_POSITION,
    SERVICE_SET_COVER_TILT_POSITION,
    SERVICE_STOP_COVER,
    STATE_CLOSED,
    STATE_CLOSING,
    STATE_OPEN,
    STATE_OPENING,
)

from . import TYPES
from .accessories import HomeAccessory, debounce
from .const import (
    CHAR_CURRENT_DOOR_STATE,
    CHAR_CURRENT_POSITION,
    CHAR_CURRENT_TILT_ANGLE,
    CHAR_POSITION_STATE,
    CHAR_TARGET_DOOR_STATE,
    CHAR_TARGET_POSITION,
    CHAR_TARGET_TILT_ANGLE,
    DEVICE_PRECISION_LEEWAY,
    SERV_GARAGE_DOOR_OPENER,
    SERV_WINDOW_COVERING,
)

_LOGGER = logging.getLogger(__name__)


@TYPES.register("GarageDoorOpener")
class GarageDoorOpener(HomeAccessory):
    """Generate a Garage Door Opener accessory for a cover entity.

    The cover entity must be in the 'garage' device class
    and support no more than open, close, and stop.
    """

    def __init__(self, *args):
        """Initialize a GarageDoorOpener accessory object."""
        super().__init__(*args, category=CATEGORY_GARAGE_DOOR_OPENER)
        self._flag_state = False

        serv_garage_door = self.add_preload_service(SERV_GARAGE_DOOR_OPENER)
        self.char_current_state = serv_garage_door.configure_char(
            CHAR_CURRENT_DOOR_STATE, value=0
        )
        self.char_target_state = serv_garage_door.configure_char(
            CHAR_TARGET_DOOR_STATE, value=0, setter_callback=self.set_state
        )

    def set_state(self, value):
        """Change garage state if call came from HomeKit."""
        _LOGGER.debug("%s: Set state to %d", self.entity_id, value)
        self._flag_state = True

        params = {ATTR_ENTITY_ID: self.entity_id}
        if value == 0:
            if self.char_current_state.value != value:
                self.char_current_state.set_value(3)
            self.call_service(DOMAIN, SERVICE_OPEN_COVER, params)
        elif value == 1:
            if self.char_current_state.value != value:
                self.char_current_state.set_value(2)
            self.call_service(DOMAIN, SERVICE_CLOSE_COVER, params)

    def update_state(self, new_state):
        """Update cover state after state changed."""
        hass_state = new_state.state
        if hass_state in (STATE_OPEN, STATE_CLOSED):
            current_state = 0 if hass_state == STATE_OPEN else 1
            self.char_current_state.set_value(current_state)
            if not self._flag_state:
                self.char_target_state.set_value(current_state)
            self._flag_state = False


@TYPES.register("WindowCovering")
class WindowCovering(HomeAccessory):
    """Generate a Window accessory for a cover entity.

    The cover entity must support: set_cover_position.
    """

    def __init__(self, *args):
        """Initialize a WindowCovering accessory object."""
        super().__init__(*args, category=CATEGORY_WINDOW_COVERING)

        self._homekit_target = None
        self._homekit_target_tilt = None

        serv_cover = self.add_preload_service(
            SERV_WINDOW_COVERING,
            chars=[CHAR_TARGET_TILT_ANGLE, CHAR_CURRENT_TILT_ANGLE],
        )

        features = self.hass.states.get(self.entity_id).attributes.get(
            ATTR_SUPPORTED_FEATURES, 0
        )

        self._supports_tilt = features & SUPPORT_SET_TILT_POSITION
        if self._supports_tilt:
            self.char_target_tilt = serv_cover.configure_char(
                CHAR_TARGET_TILT_ANGLE, setter_callback=self.set_tilt
            )
            self.char_current_tilt = serv_cover.configure_char(
                CHAR_CURRENT_TILT_ANGLE, value=0
            )

        self.char_current_position = serv_cover.configure_char(
            CHAR_CURRENT_POSITION, value=0
        )
        self.char_target_position = serv_cover.configure_char(
            CHAR_TARGET_POSITION, value=0, setter_callback=self.move_cover
        )
        self.char_position_state = serv_cover.configure_char(
            CHAR_POSITION_STATE, value=2
        )

    @debounce
    def set_tilt(self, value):
        """Set tilt to value if call came from HomeKit."""
        self._homekit_target_tilt = value
        _LOGGER.info("%s: Set tilt to %d", self.entity_id, value)

        # HomeKit sends values between -90 and 90.
        # We'll have to normalize to [0,100]
        value = round((value + 90) / 180.0 * 100.0)

        params = {ATTR_ENTITY_ID: self.entity_id, ATTR_TILT_POSITION: value}

        self.call_service(DOMAIN, SERVICE_SET_COVER_TILT_POSITION, params, value)

    @debounce
    def move_cover(self, value):
        """Move cover to value if call came from HomeKit."""
        _LOGGER.debug("%s: Set position to %d", self.entity_id, value)
        self._homekit_target = value

        params = {ATTR_ENTITY_ID: self.entity_id, ATTR_POSITION: value}
        self.call_service(DOMAIN, SERVICE_SET_COVER_POSITION, params, value)

    def update_state(self, new_state):
        """Update cover position and tilt after state changed."""
        current_position = new_state.attributes.get(ATTR_CURRENT_POSITION)
        if isinstance(current_position, (float, int)):
            current_position = int(current_position)
            self.char_current_position.set_value(current_position)

            # We have to assume that the device has worse precision than HomeKit.
            # If it reports back a state that is only _close_ to HK's requested
            # state, we'll "fix" what HomeKit requested so that it won't appear
            # out of sync.
            if (
                self._homekit_target is None
                or abs(current_position - self._homekit_target)
                < DEVICE_PRECISION_LEEWAY
            ):
                self.char_target_position.set_value(current_position)
                self._homekit_target = None
        if new_state.state == STATE_OPENING:
            self.char_position_state.set_value(1)
        elif new_state.state == STATE_CLOSING:
            self.char_position_state.set_value(0)
        else:
            self.char_position_state.set_value(2)

        # update tilt
        current_tilt = new_state.attributes.get(ATTR_CURRENT_TILT_POSITION)
        if isinstance(current_tilt, (float, int)):
            # HomeKit sends values between -90 and 90.
            # We'll have to normalize to [0,100]
            current_tilt = (current_tilt / 100.0 * 180.0) - 90.0
            current_tilt = int(current_tilt)
            self.char_current_tilt.set_value(current_tilt)

            # We have to assume that the device has worse precision than HomeKit.
            # If it reports back a state that is only _close_ to HK's requested
            # state, we'll "fix" what HomeKit requested so that it won't appear
            # out of sync.
            if self._homekit_target_tilt is None or abs(
                current_tilt - self._homekit_target_tilt < DEVICE_PRECISION_LEEWAY
            ):
                self.char_target_tilt.set_value(current_tilt)
                self._homekit_target_tilt = None


@TYPES.register("WindowCoveringBasic")
class WindowCoveringBasic(HomeAccessory):
    """Generate a Window accessory for a cover entity.

    The cover entity must support: open_cover, close_cover,
    stop_cover (optional).
    """

    def __init__(self, *args):
        """Initialize a WindowCovering accessory object."""
        super().__init__(*args, category=CATEGORY_WINDOW_COVERING)
        features = self.hass.states.get(self.entity_id).attributes.get(
            ATTR_SUPPORTED_FEATURES
        )
        self._supports_stop = features & SUPPORT_STOP

        serv_cover = self.add_preload_service(SERV_WINDOW_COVERING)
        self.char_current_position = serv_cover.configure_char(
            CHAR_CURRENT_POSITION, value=0
        )
        self.char_target_position = serv_cover.configure_char(
            CHAR_TARGET_POSITION, value=0, setter_callback=self.move_cover
        )
        self.char_position_state = serv_cover.configure_char(
            CHAR_POSITION_STATE, value=2
        )

    @debounce
    def move_cover(self, value):
        """Move cover to value if call came from HomeKit."""
        _LOGGER.debug("%s: Set position to %d", self.entity_id, value)

        if self._supports_stop:
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

        params = {ATTR_ENTITY_ID: self.entity_id}
        self.call_service(DOMAIN, service, params)

        # Snap the current/target position to the expected final position.
        self.char_current_position.set_value(position)
        self.char_target_position.set_value(position)

    def update_state(self, new_state):
        """Update cover position after state changed."""
        position_mapping = {STATE_OPEN: 100, STATE_CLOSED: 0}
        hk_position = position_mapping.get(new_state.state)
        if hk_position is not None:
            self.char_current_position.set_value(hk_position)
            self.char_target_position.set_value(hk_position)
        if new_state.state == STATE_OPENING:
            self.char_position_state.set_value(1)
        elif new_state.state == STATE_CLOSING:
            self.char_position_state.set_value(0)
        else:
            self.char_position_state.set_value(2)
