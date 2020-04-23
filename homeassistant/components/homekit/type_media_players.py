"""Class to hold all media player accessories."""
import logging

from pyhap.const import CATEGORY_SWITCH, CATEGORY_TELEVISION

from homeassistant.components.media_player import (
    ATTR_INPUT_SOURCE,
    ATTR_INPUT_SOURCE_LIST,
    ATTR_MEDIA_VOLUME_LEVEL,
    ATTR_MEDIA_VOLUME_MUTED,
    DOMAIN,
    SERVICE_SELECT_SOURCE,
    SUPPORT_PAUSE,
    SUPPORT_PLAY,
    SUPPORT_SELECT_SOURCE,
    SUPPORT_VOLUME_MUTE,
    SUPPORT_VOLUME_SET,
    SUPPORT_VOLUME_STEP,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    SERVICE_MEDIA_PAUSE,
    SERVICE_MEDIA_PLAY,
    SERVICE_MEDIA_PLAY_PAUSE,
    SERVICE_MEDIA_STOP,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    SERVICE_VOLUME_DOWN,
    SERVICE_VOLUME_MUTE,
    SERVICE_VOLUME_SET,
    SERVICE_VOLUME_UP,
    STATE_OFF,
    STATE_PAUSED,
    STATE_PLAYING,
    STATE_STANDBY,
    STATE_UNKNOWN,
)

from . import TYPES
from .accessories import HomeAccessory
from .const import (
    CHAR_ACTIVE,
    CHAR_ACTIVE_IDENTIFIER,
    CHAR_CONFIGURED_NAME,
    CHAR_CURRENT_VISIBILITY_STATE,
    CHAR_IDENTIFIER,
    CHAR_INPUT_SOURCE_TYPE,
    CHAR_IS_CONFIGURED,
    CHAR_MUTE,
    CHAR_NAME,
    CHAR_ON,
    CHAR_REMOTE_KEY,
    CHAR_SLEEP_DISCOVER_MODE,
    CHAR_VOLUME,
    CHAR_VOLUME_CONTROL_TYPE,
    CHAR_VOLUME_SELECTOR,
    CONF_FEATURE_LIST,
    FEATURE_ON_OFF,
    FEATURE_PLAY_PAUSE,
    FEATURE_PLAY_STOP,
    FEATURE_TOGGLE_MUTE,
    SERV_INPUT_SOURCE,
    SERV_SWITCH,
    SERV_TELEVISION,
    SERV_TELEVISION_SPEAKER,
)

_LOGGER = logging.getLogger(__name__)

MEDIA_PLAYER_KEYS = {
    # 0: "Rewind",
    # 1: "FastForward",
    # 2: "NextTrack",
    # 3: "PreviousTrack",
    # 4: "ArrowUp",
    # 5: "ArrowDown",
    # 6: "ArrowLeft",
    # 7: "ArrowRight",
    # 8: "Select",
    # 9: "Back",
    # 10: "Exit",
    11: SERVICE_MEDIA_PLAY_PAUSE,
    # 15: "Information",
}

MODE_FRIENDLY_NAME = {
    FEATURE_ON_OFF: "Power",
    FEATURE_PLAY_PAUSE: "Play/Pause",
    FEATURE_PLAY_STOP: "Play/Stop",
    FEATURE_TOGGLE_MUTE: "Mute",
}


@TYPES.register("MediaPlayer")
class MediaPlayer(HomeAccessory):
    """Generate a Media Player accessory."""

    def __init__(self, *args):
        """Initialize a Switch accessory object."""
        super().__init__(*args, category=CATEGORY_SWITCH)
        state = self.hass.states.get(self.entity_id)
        self.chars = {
            FEATURE_ON_OFF: None,
            FEATURE_PLAY_PAUSE: None,
            FEATURE_PLAY_STOP: None,
            FEATURE_TOGGLE_MUTE: None,
        }
        feature_list = self.config[CONF_FEATURE_LIST]

        if FEATURE_ON_OFF in feature_list:
            name = self.generate_service_name(FEATURE_ON_OFF)
            serv_on_off = self.add_preload_service(SERV_SWITCH, CHAR_NAME)
            serv_on_off.configure_char(CHAR_NAME, value=name)
            self.chars[FEATURE_ON_OFF] = serv_on_off.configure_char(
                CHAR_ON, value=False, setter_callback=self.set_on_off
            )

        if FEATURE_PLAY_PAUSE in feature_list:
            name = self.generate_service_name(FEATURE_PLAY_PAUSE)
            serv_play_pause = self.add_preload_service(SERV_SWITCH, CHAR_NAME)
            serv_play_pause.configure_char(CHAR_NAME, value=name)
            self.chars[FEATURE_PLAY_PAUSE] = serv_play_pause.configure_char(
                CHAR_ON, value=False, setter_callback=self.set_play_pause
            )

        if FEATURE_PLAY_STOP in feature_list:
            name = self.generate_service_name(FEATURE_PLAY_STOP)
            serv_play_stop = self.add_preload_service(SERV_SWITCH, CHAR_NAME)
            serv_play_stop.configure_char(CHAR_NAME, value=name)
            self.chars[FEATURE_PLAY_STOP] = serv_play_stop.configure_char(
                CHAR_ON, value=False, setter_callback=self.set_play_stop
            )

        if FEATURE_TOGGLE_MUTE in feature_list:
            name = self.generate_service_name(FEATURE_TOGGLE_MUTE)
            serv_toggle_mute = self.add_preload_service(SERV_SWITCH, CHAR_NAME)
            serv_toggle_mute.configure_char(CHAR_NAME, value=name)
            self.chars[FEATURE_TOGGLE_MUTE] = serv_toggle_mute.configure_char(
                CHAR_ON, value=False, setter_callback=self.set_toggle_mute
            )
        self.update_state(state)

    def generate_service_name(self, mode):
        """Generate name for individual service."""
        return f"{self.display_name} {MODE_FRIENDLY_NAME[mode]}"

    def set_on_off(self, value):
        """Move switch state to value if call came from HomeKit."""
        _LOGGER.debug('%s: Set switch state for "on_off" to %s', self.entity_id, value)
        service = SERVICE_TURN_ON if value else SERVICE_TURN_OFF
        params = {ATTR_ENTITY_ID: self.entity_id}
        self.call_service(DOMAIN, service, params)

    def set_play_pause(self, value):
        """Move switch state to value if call came from HomeKit."""
        _LOGGER.debug(
            '%s: Set switch state for "play_pause" to %s', self.entity_id, value
        )
        service = SERVICE_MEDIA_PLAY if value else SERVICE_MEDIA_PAUSE
        params = {ATTR_ENTITY_ID: self.entity_id}
        self.call_service(DOMAIN, service, params)

    def set_play_stop(self, value):
        """Move switch state to value if call came from HomeKit."""
        _LOGGER.debug(
            '%s: Set switch state for "play_stop" to %s', self.entity_id, value
        )
        service = SERVICE_MEDIA_PLAY if value else SERVICE_MEDIA_STOP
        params = {ATTR_ENTITY_ID: self.entity_id}
        self.call_service(DOMAIN, service, params)

    def set_toggle_mute(self, value):
        """Move switch state to value if call came from HomeKit."""
        _LOGGER.debug(
            '%s: Set switch state for "toggle_mute" to %s', self.entity_id, value
        )
        params = {ATTR_ENTITY_ID: self.entity_id, ATTR_MEDIA_VOLUME_MUTED: value}
        self.call_service(DOMAIN, SERVICE_VOLUME_MUTE, params)

    def update_state(self, new_state):
        """Update switch state after state changed."""
        current_state = new_state.state

        if self.chars[FEATURE_ON_OFF]:
            hk_state = current_state not in (
                STATE_OFF,
                STATE_UNKNOWN,
                STATE_STANDBY,
                "None",
            )
            _LOGGER.debug(
                '%s: Set current state for "on_off" to %s', self.entity_id, hk_state
            )
            if self.chars[FEATURE_ON_OFF].value != hk_state:
                self.chars[FEATURE_ON_OFF].set_value(hk_state)

        if self.chars[FEATURE_PLAY_PAUSE]:
            hk_state = current_state == STATE_PLAYING
            _LOGGER.debug(
                '%s: Set current state for "play_pause" to %s',
                self.entity_id,
                hk_state,
            )
            if self.chars[FEATURE_PLAY_PAUSE].value != hk_state:
                self.chars[FEATURE_PLAY_PAUSE].set_value(hk_state)

        if self.chars[FEATURE_PLAY_STOP]:
            hk_state = current_state == STATE_PLAYING
            _LOGGER.debug(
                '%s: Set current state for "play_stop" to %s', self.entity_id, hk_state,
            )
            if self.chars[FEATURE_PLAY_STOP].value != hk_state:
                self.chars[FEATURE_PLAY_STOP].set_value(hk_state)

        if self.chars[FEATURE_TOGGLE_MUTE]:
            current_state = new_state.attributes.get(ATTR_MEDIA_VOLUME_MUTED)
            _LOGGER.debug(
                '%s: Set current state for "toggle_mute" to %s',
                self.entity_id,
                current_state,
            )
            if self.chars[FEATURE_TOGGLE_MUTE].value != current_state:
                self.chars[FEATURE_TOGGLE_MUTE].set_value(current_state)


@TYPES.register("TelevisionMediaPlayer")
class TelevisionMediaPlayer(HomeAccessory):
    """Generate a Television Media Player accessory."""

    def __init__(self, *args):
        """Initialize a Switch accessory object."""
        super().__init__(*args, category=CATEGORY_TELEVISION)
        state = self.hass.states.get(self.entity_id)

        self.support_select_source = False

        self.sources = []

        # Add additional characteristics if volume or input selection supported
        self.chars_tv = []
        self.chars_speaker = []
        features = self.hass.states.get(self.entity_id).attributes.get(
            ATTR_SUPPORTED_FEATURES, 0
        )

        if features & (SUPPORT_PLAY | SUPPORT_PAUSE):
            self.chars_tv.append(CHAR_REMOTE_KEY)
        if features & SUPPORT_VOLUME_MUTE or features & SUPPORT_VOLUME_STEP:
            self.chars_speaker.extend(
                (CHAR_NAME, CHAR_ACTIVE, CHAR_VOLUME_CONTROL_TYPE, CHAR_VOLUME_SELECTOR)
            )
            if features & SUPPORT_VOLUME_SET:
                self.chars_speaker.append(CHAR_VOLUME)

        if features & SUPPORT_SELECT_SOURCE:
            self.support_select_source = True

        serv_tv = self.add_preload_service(SERV_TELEVISION, self.chars_tv)
        self.set_primary_service(serv_tv)
        serv_tv.configure_char(CHAR_CONFIGURED_NAME, value=self.display_name)
        serv_tv.configure_char(CHAR_SLEEP_DISCOVER_MODE, value=True)
        self.char_active = serv_tv.configure_char(
            CHAR_ACTIVE, setter_callback=self.set_on_off
        )

        if CHAR_REMOTE_KEY in self.chars_tv:
            self.char_remote_key = serv_tv.configure_char(
                CHAR_REMOTE_KEY, setter_callback=self.set_remote_key
            )

        if CHAR_VOLUME_SELECTOR in self.chars_speaker:
            serv_speaker = self.add_preload_service(
                SERV_TELEVISION_SPEAKER, self.chars_speaker
            )
            serv_tv.add_linked_service(serv_speaker)

            name = f"{self.display_name} Volume"
            serv_speaker.configure_char(CHAR_NAME, value=name)
            serv_speaker.configure_char(CHAR_ACTIVE, value=1)

            self.char_mute = serv_speaker.configure_char(
                CHAR_MUTE, value=False, setter_callback=self.set_mute
            )

            volume_control_type = 1 if CHAR_VOLUME in self.chars_speaker else 2
            serv_speaker.configure_char(
                CHAR_VOLUME_CONTROL_TYPE, value=volume_control_type
            )

            self.char_volume_selector = serv_speaker.configure_char(
                CHAR_VOLUME_SELECTOR, setter_callback=self.set_volume_step
            )

            if CHAR_VOLUME in self.chars_speaker:
                self.char_volume = serv_speaker.configure_char(
                    CHAR_VOLUME, setter_callback=self.set_volume
                )

        if self.support_select_source:
            self.sources = self.hass.states.get(self.entity_id).attributes.get(
                ATTR_INPUT_SOURCE_LIST, []
            )
            self.char_input_source = serv_tv.configure_char(
                CHAR_ACTIVE_IDENTIFIER, setter_callback=self.set_input_source
            )
            for index, source in enumerate(self.sources):
                serv_input = self.add_preload_service(
                    SERV_INPUT_SOURCE, [CHAR_IDENTIFIER, CHAR_NAME]
                )
                serv_tv.add_linked_service(serv_input)
                serv_input.configure_char(CHAR_CONFIGURED_NAME, value=source)
                serv_input.configure_char(CHAR_NAME, value=source)
                serv_input.configure_char(CHAR_IDENTIFIER, value=index)
                serv_input.configure_char(CHAR_IS_CONFIGURED, value=True)
                input_type = 3 if "hdmi" in source.lower() else 0
                serv_input.configure_char(CHAR_INPUT_SOURCE_TYPE, value=input_type)
                serv_input.configure_char(CHAR_CURRENT_VISIBILITY_STATE, value=False)
                _LOGGER.debug("%s: Added source %s.", self.entity_id, source)

        self.update_state(state)

    def set_on_off(self, value):
        """Move switch state to value if call came from HomeKit."""
        _LOGGER.debug('%s: Set switch state for "on_off" to %s', self.entity_id, value)
        service = SERVICE_TURN_ON if value else SERVICE_TURN_OFF
        params = {ATTR_ENTITY_ID: self.entity_id}
        self.call_service(DOMAIN, service, params)

    def set_mute(self, value):
        """Move switch state to value if call came from HomeKit."""
        _LOGGER.debug(
            '%s: Set switch state for "toggle_mute" to %s', self.entity_id, value
        )
        params = {ATTR_ENTITY_ID: self.entity_id, ATTR_MEDIA_VOLUME_MUTED: value}
        self.call_service(DOMAIN, SERVICE_VOLUME_MUTE, params)

    def set_volume(self, value):
        """Send volume step value if call came from HomeKit."""
        _LOGGER.debug("%s: Set volume to %s", self.entity_id, value)
        params = {ATTR_ENTITY_ID: self.entity_id, ATTR_MEDIA_VOLUME_LEVEL: value}
        self.call_service(DOMAIN, SERVICE_VOLUME_SET, params)

    def set_volume_step(self, value):
        """Send volume step value if call came from HomeKit."""
        _LOGGER.debug("%s: Step volume by %s", self.entity_id, value)
        service = SERVICE_VOLUME_DOWN if value else SERVICE_VOLUME_UP
        params = {ATTR_ENTITY_ID: self.entity_id}
        self.call_service(DOMAIN, service, params)

    def set_input_source(self, value):
        """Send input set value if call came from HomeKit."""
        _LOGGER.debug("%s: Set current input to %s", self.entity_id, value)
        source = self.sources[value]
        params = {ATTR_ENTITY_ID: self.entity_id, ATTR_INPUT_SOURCE: source}
        self.call_service(DOMAIN, SERVICE_SELECT_SOURCE, params)

    def set_remote_key(self, value):
        """Send remote key value if call came from HomeKit."""
        _LOGGER.debug("%s: Set remote key to %s", self.entity_id, value)
        service = MEDIA_PLAYER_KEYS.get(value)
        if service:
            # Handle Play Pause
            if service == SERVICE_MEDIA_PLAY_PAUSE:
                state = self.hass.states.get(self.entity_id).state
                if state in (STATE_PLAYING, STATE_PAUSED):
                    service = (
                        SERVICE_MEDIA_PLAY
                        if state == STATE_PAUSED
                        else SERVICE_MEDIA_PAUSE
                    )
            params = {ATTR_ENTITY_ID: self.entity_id}
            self.call_service(DOMAIN, service, params)

    def update_state(self, new_state):
        """Update Television state after state changed."""
        current_state = new_state.state

        # Power state television
        hk_state = 0
        if current_state not in ("None", STATE_OFF, STATE_UNKNOWN):
            hk_state = 1

        _LOGGER.debug("%s: Set current active state to %s", self.entity_id, hk_state)
        if self.char_active.value != hk_state:
            self.char_active.set_value(hk_state)

        # Set mute state
        if CHAR_VOLUME_SELECTOR in self.chars_speaker:
            current_mute_state = new_state.attributes.get(ATTR_MEDIA_VOLUME_MUTED)
            _LOGGER.debug(
                "%s: Set current mute state to %s", self.entity_id, current_mute_state,
            )
            if self.char_mute.value != current_mute_state:
                self.char_mute.set_value(current_mute_state)

        # Set active input
        if self.support_select_source:
            source_name = new_state.attributes.get(ATTR_INPUT_SOURCE)
            if self.sources:
                _LOGGER.debug(
                    "%s: Set current input to %s", self.entity_id, source_name
                )
                if source_name in self.sources:
                    index = self.sources.index(source_name)
                    if self.char_input_source.value != index:
                        self.char_input_source.set_value(index)
                else:
                    _LOGGER.warning(
                        "%s: Sources out of sync. Restart Home Assistant",
                        self.entity_id,
                    )
                    if self.char_input_source.value != 0:
                        self.char_input_source.set_value(0)
