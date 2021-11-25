"""Class to hold remote accessories."""
from abc import abstractmethod
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
    ATTR_SUPPORTED_FEATURES,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_ON,
)
from homeassistant.core import callback

from .accessories import TYPES, HomeAccessory
from .const import (
    ATTR_KEY_NAME,
    CHAR_ACTIVE,
    CHAR_ACTIVE_IDENTIFIER,
    CHAR_CONFIGURED_NAME,
    CHAR_CURRENT_VISIBILITY_STATE,
    CHAR_IDENTIFIER,
    CHAR_INPUT_SOURCE_TYPE,
    CHAR_IS_CONFIGURED,
    CHAR_NAME,
    CHAR_REMOTE_KEY,
    CHAR_SLEEP_DISCOVER_MODE,
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
    MAX_NAME_LENGTH,
    SERV_INPUT_SOURCE,
    SERV_TELEVISION,
)

MAXIMUM_SOURCES = (
    90  # Maximum services per accessory is 100. The base acccessory uses 9
)

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


class RemoteInputSelectAccessory(HomeAccessory):
    """Generate a InputSelect accessory."""

    def __init__(
        self,
        required_feature,
        source_key,
        source_list_key,
        *args,
        **kwargs,
    ):
        """Initialize a InputSelect accessory object."""
        super().__init__(*args, category=CATEGORY_TELEVISION, **kwargs)
        state = self.hass.states.get(self.entity_id)
        features = state.attributes.get(ATTR_SUPPORTED_FEATURES, 0)

        self.source_key = source_key
        self.source_list_key = source_list_key
        self.sources = []
        self.support_select_source = False
        if features & required_feature:
            sources = state.attributes.get(source_list_key, [])
            if len(sources) > MAXIMUM_SOURCES:
                _LOGGER.warning(
                    "%s: Reached maximum number of sources (%s)",
                    self.entity_id,
                    MAXIMUM_SOURCES,
                )
            self.sources = sources[:MAXIMUM_SOURCES]
            if self.sources:
                self.support_select_source = True

        self.chars_tv = [CHAR_REMOTE_KEY]
        serv_tv = self.serv_tv = self.add_preload_service(
            SERV_TELEVISION, self.chars_tv
        )
        self.char_remote_key = self.serv_tv.configure_char(
            CHAR_REMOTE_KEY, setter_callback=self.set_remote_key
        )
        self.set_primary_service(serv_tv)
        serv_tv.configure_char(CHAR_CONFIGURED_NAME, value=self.display_name)
        serv_tv.configure_char(CHAR_SLEEP_DISCOVER_MODE, value=True)
        self.char_active = serv_tv.configure_char(
            CHAR_ACTIVE, setter_callback=self.set_on_off
        )

        if not self.support_select_source:
            return

        self.char_input_source = serv_tv.configure_char(
            CHAR_ACTIVE_IDENTIFIER, setter_callback=self.set_input_source
        )
        for index, source in enumerate(self.sources):
            serv_input = self.add_preload_service(
                SERV_INPUT_SOURCE, [CHAR_IDENTIFIER, CHAR_NAME]
            )
            serv_tv.add_linked_service(serv_input)
            serv_input.configure_char(
                CHAR_CONFIGURED_NAME, value=source[:MAX_NAME_LENGTH]
            )
            serv_input.configure_char(CHAR_NAME, value=source[:MAX_NAME_LENGTH])
            serv_input.configure_char(CHAR_IDENTIFIER, value=index)
            serv_input.configure_char(CHAR_IS_CONFIGURED, value=True)
            input_type = 3 if "hdmi" in source.lower() else 0
            serv_input.configure_char(CHAR_INPUT_SOURCE_TYPE, value=input_type)
            serv_input.configure_char(CHAR_CURRENT_VISIBILITY_STATE, value=False)
            _LOGGER.debug("%s: Added source %s", self.entity_id, source)

    @abstractmethod
    def set_on_off(self, value):
        """Move switch state to value if call came from HomeKit."""

    @abstractmethod
    def set_input_source(self, value):
        """Send input set value if call came from HomeKit."""

    @abstractmethod
    def set_remote_key(self, value):
        """Send remote key value if call came from HomeKit."""

    @callback
    def _async_update_input_state(self, hk_state, new_state):
        """Update input state after state changed."""
        # Set active input
        if not self.support_select_source or not self.sources:
            return
        source_name = new_state.attributes.get(self.source_key)
        _LOGGER.debug("%s: Set current input to %s", self.entity_id, source_name)
        if source_name in self.sources:
            index = self.sources.index(source_name)
            self.char_input_source.set_value(index)
            return

        possible_sources = new_state.attributes.get(self.source_list_key, [])
        if source_name in possible_sources:
            index = possible_sources.index(source_name)
            if index >= MAXIMUM_SOURCES:
                _LOGGER.debug(
                    "%s: Source %s and above are not supported",
                    self.entity_id,
                    MAXIMUM_SOURCES,
                )
            else:
                _LOGGER.debug(
                    "%s: Sources out of sync. Rebuilding Accessory",
                    self.entity_id,
                )
                # Sources are out of sync, recreate the accessory
                self.async_reset()
                return

        _LOGGER.debug(
            "%s: Source %s does not exist the source list: %s",
            self.entity_id,
            source_name,
            possible_sources,
        )
        self.char_input_source.set_value(0)


@TYPES.register("ActivityRemote")
class ActivityRemote(RemoteInputSelectAccessory):
    """Generate a Activity Remote accessory."""

    def __init__(self, *args):
        """Initialize a Activity Remote accessory object."""
        super().__init__(
            SUPPORT_ACTIVITY,
            ATTR_CURRENT_ACTIVITY,
            ATTR_ACTIVITY_LIST,
            *args,
        )
        self.async_update_state(self.hass.states.get(self.entity_id))

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
        if (key_name := REMOTE_KEYS.get(value)) is None:
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
        self.char_active.set_value(hk_state)

        self._async_update_input_state(hk_state, new_state)
