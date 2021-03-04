"""Class to hold remote accessories."""
import logging

from pyhap.const import CATEGORY_TELEVISION

from homeassistant.components.remote import (
    ATTR_ACTIVITY,
    ATTR_ACTIVITY_LIST,
    ATTR_CURRENT_ACTIVITY,
    DOMAIN as REMOTE_DOMAIN,
    SUPPORT_ACTIVITY,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_ON,
)
from homeassistant.core import callback

from .accessories import TYPES
from .const import (
    ATTR_KEY_NAME,
    EVENT_HOMEKIT_TV_REMOTE_KEY_PRESSED,
    KEY_ARROW_DOWN,
    KEY_ARROW_LEFT,
    KEY_ARROW_RIGHT,
    KEY_ARROW_UP,
    KEY_BACK,
    KEY_EXIT,
    KEY_FAST_FORWARD,
    KEY_INFORMATION,
    KEY_NEXT_TRACK,
    KEY_PLAY_PAUSE,
    KEY_PREVIOUS_TRACK,
    KEY_REWIND,
    KEY_SELECT,
)
from .type_input_select import InputSelectAccessory

_LOGGER = logging.getLogger(__name__)

REMOTE_KEYS = {
    0: KEY_REWIND,
    1: KEY_FAST_FORWARD,
    2: KEY_NEXT_TRACK,
    3: KEY_PREVIOUS_TRACK,
    4: KEY_ARROW_UP,
    5: KEY_ARROW_DOWN,
    6: KEY_ARROW_LEFT,
    7: KEY_ARROW_RIGHT,
    8: KEY_SELECT,
    9: KEY_BACK,
    10: KEY_EXIT,
    11: KEY_PLAY_PAUSE,
    15: KEY_INFORMATION,
}


@TYPES.register("ActivityRemote")
class ActivityRemote(InputSelectAccessory):
    """Generate a Activity Remote accessory."""

    def __init__(self, *args):
        """Initialize a Activity Remote accessory object."""
        super().__init__(
            SUPPORT_ACTIVITY,
            ATTR_CURRENT_ACTIVITY,
            ATTR_ACTIVITY_LIST,
            *args,
        )
        state = self.hass.states.get(self.entity_id)
        self.async_update_state(state)

    def set_on_off(self, value):
        """Move switch state to value if call came from HomeKit."""
        _LOGGER.debug('%s: Set switch state for "on_off" to %s', self.entity_id, value)
        service = SERVICE_TURN_ON if value else SERVICE_TURN_OFF
        params = {ATTR_ENTITY_ID: self.entity_id}
        self.async_call_service(REMOTE_DOMAIN, service, params)

    def set_input_source(self, value):
        """Send input set value if call came from HomeKit."""
        _LOGGER.debug("%s: Set current input to %s", self.entity_id, value)
        source = self.sources[value]
        params = {ATTR_ENTITY_ID: self.entity_id, ATTR_ACTIVITY: source}
        self.async_call_service(REMOTE_DOMAIN, SERVICE_TURN_ON, params)

    def set_remote_key(self, value):
        """Send remote key value if call came from HomeKit."""
        _LOGGER.debug("%s: Set remote key to %s", self.entity_id, value)
        key_name = REMOTE_KEYS.get(value)
        if key_name is None:
            _LOGGER.warning("%s: Unhandled key press for %s", self.entity_id, value)
            return
        self.hass.bus.async_fire(
            EVENT_HOMEKIT_TV_REMOTE_KEY_PRESSED,
            {ATTR_KEY_NAME: key_name, ATTR_ENTITY_ID: self.entity_id},
        )

    @callback
    def async_update_state(self, new_state):
        """Update Television remote state after state changed."""
        current_state = new_state.state
        # Power state remote
        hk_state = 1 if current_state == STATE_ON else 0
        _LOGGER.debug("%s: Set current active state to %s", self.entity_id, hk_state)
        if self.char_active.value != hk_state:
            self.char_active.set_value(hk_state)

        self._async_update_input_state(hk_state, new_state)


class RemoteInputSelectAccessory(InputSelectAccessory):
    """Generate a InputSelect accessory that includes a remote control."""

    def __init__(self, required_feature, source_key, source_list_key, *args):
        """Init a InputSelect accessory that includes a remote control."""
        super().__init__(
            required_feature,
            source_key,
            source_list_key,
            has_remote=True,
            category=CATEGORY_TELEVISION,
        )
