"""Class to hold all media player accessories."""
import logging
from typing import Any

from pyhap.characteristic import Characteristic
from pyhap.const import CATEGORY_SWITCH

from homeassistant.components.media_player import (
    ATTR_INPUT_SOURCE,
    ATTR_INPUT_SOURCE_LIST,
    ATTR_MEDIA_VOLUME_LEVEL,
    ATTR_MEDIA_VOLUME_MUTED,
    DOMAIN,
    SERVICE_SELECT_SOURCE,
    MediaPlayerEntityFeature,
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
from homeassistant.core import State, callback

from .accessories import TYPES, HomeAccessory
from .const import (
    ATTR_KEY_NAME,
    CATEGORY_RECEIVER,
    CHAR_ACTIVE,
    CHAR_MUTE,
    CHAR_NAME,
    CHAR_ON,
    CHAR_VOLUME,
    CHAR_VOLUME_CONTROL_TYPE,
    CHAR_VOLUME_SELECTOR,
    CONF_FEATURE_LIST,
    EVENT_HOMEKIT_TV_REMOTE_KEY_PRESSED,
    FEATURE_ON_OFF,
    FEATURE_PLAY_PAUSE,
    FEATURE_PLAY_STOP,
    FEATURE_TOGGLE_MUTE,
    KEY_PLAY_PAUSE,
    SERV_SWITCH,
    SERV_TELEVISION_SPEAKER,
)
from .type_remotes import REMOTE_KEYS, RemoteInputSelectAccessory
from .util import cleanup_name_for_homekit, get_media_player_features

_LOGGER = logging.getLogger(__name__)


# Names may not contain special characters
# or emjoi (/ is a special character for Apple)
MODE_FRIENDLY_NAME = {
    FEATURE_ON_OFF: "Power",
    FEATURE_PLAY_PAUSE: "Play-Pause",
    FEATURE_PLAY_STOP: "Play-Stop",
    FEATURE_TOGGLE_MUTE: "Mute",
}

MEDIA_PLAYER_OFF_STATES = (
    STATE_OFF,
    STATE_UNKNOWN,
    STATE_STANDBY,
    "None",
)


@TYPES.register("MediaPlayer")
class MediaPlayer(HomeAccessory):
    """Generate a Media Player accessory."""

    def __init__(self, *args: Any) -> None:
        """Initialize a Switch accessory object."""
        super().__init__(*args, category=CATEGORY_SWITCH)
        state = self.hass.states.get(self.entity_id)
        assert state
        self.chars: dict[str, Characteristic | None] = {
            FEATURE_ON_OFF: None,
            FEATURE_PLAY_PAUSE: None,
            FEATURE_PLAY_STOP: None,
            FEATURE_TOGGLE_MUTE: None,
        }
        feature_list = self.config.get(
            CONF_FEATURE_LIST, get_media_player_features(state)
        )

        if FEATURE_ON_OFF in feature_list:
            name = self.generate_service_name(FEATURE_ON_OFF)
            serv_on_off = self.add_preload_service(
                SERV_SWITCH, CHAR_NAME, unique_id=FEATURE_ON_OFF
            )
            serv_on_off.configure_char(CHAR_NAME, value=name)
            self.chars[FEATURE_ON_OFF] = serv_on_off.configure_char(
                CHAR_ON, value=False, setter_callback=self.set_on_off
            )

        if FEATURE_PLAY_PAUSE in feature_list:
            name = self.generate_service_name(FEATURE_PLAY_PAUSE)
            serv_play_pause = self.add_preload_service(
                SERV_SWITCH, CHAR_NAME, unique_id=FEATURE_PLAY_PAUSE
            )
            serv_play_pause.configure_char(CHAR_NAME, value=name)
            self.chars[FEATURE_PLAY_PAUSE] = serv_play_pause.configure_char(
                CHAR_ON, value=False, setter_callback=self.set_play_pause
            )

        if FEATURE_PLAY_STOP in feature_list:
            name = self.generate_service_name(FEATURE_PLAY_STOP)
            serv_play_stop = self.add_preload_service(
                SERV_SWITCH, CHAR_NAME, unique_id=FEATURE_PLAY_STOP
            )
            serv_play_stop.configure_char(CHAR_NAME, value=name)
            self.chars[FEATURE_PLAY_STOP] = serv_play_stop.configure_char(
                CHAR_ON, value=False, setter_callback=self.set_play_stop
            )

        if FEATURE_TOGGLE_MUTE in feature_list:
            name = self.generate_service_name(FEATURE_TOGGLE_MUTE)
            serv_toggle_mute = self.add_preload_service(
                SERV_SWITCH, CHAR_NAME, unique_id=FEATURE_TOGGLE_MUTE
            )
            serv_toggle_mute.configure_char(CHAR_NAME, value=name)
            self.chars[FEATURE_TOGGLE_MUTE] = serv_toggle_mute.configure_char(
                CHAR_ON, value=False, setter_callback=self.set_toggle_mute
            )
        self.async_update_state(state)

    def generate_service_name(self, mode: str) -> str:
        """Generate name for individual service."""
        return cleanup_name_for_homekit(
            f"{self.display_name} {MODE_FRIENDLY_NAME[mode]}"
        )

    def set_on_off(self, value: bool) -> None:
        """Move switch state to value if call came from HomeKit."""
        _LOGGER.debug('%s: Set switch state for "on_off" to %s', self.entity_id, value)
        service = SERVICE_TURN_ON if value else SERVICE_TURN_OFF
        params = {ATTR_ENTITY_ID: self.entity_id}
        self.async_call_service(DOMAIN, service, params)

    def set_play_pause(self, value: bool) -> None:
        """Move switch state to value if call came from HomeKit."""
        _LOGGER.debug(
            '%s: Set switch state for "play_pause" to %s', self.entity_id, value
        )
        service = SERVICE_MEDIA_PLAY if value else SERVICE_MEDIA_PAUSE
        params = {ATTR_ENTITY_ID: self.entity_id}
        self.async_call_service(DOMAIN, service, params)

    def set_play_stop(self, value: bool) -> None:
        """Move switch state to value if call came from HomeKit."""
        _LOGGER.debug(
            '%s: Set switch state for "play_stop" to %s', self.entity_id, value
        )
        service = SERVICE_MEDIA_PLAY if value else SERVICE_MEDIA_STOP
        params = {ATTR_ENTITY_ID: self.entity_id}
        self.async_call_service(DOMAIN, service, params)

    def set_toggle_mute(self, value: bool) -> None:
        """Move switch state to value if call came from HomeKit."""
        _LOGGER.debug(
            '%s: Set switch state for "toggle_mute" to %s', self.entity_id, value
        )
        params = {ATTR_ENTITY_ID: self.entity_id, ATTR_MEDIA_VOLUME_MUTED: value}
        self.async_call_service(DOMAIN, SERVICE_VOLUME_MUTE, params)

    @callback
    def async_update_state(self, new_state: State) -> None:
        """Update switch state after state changed."""
        current_state = new_state.state

        if on_off_char := self.chars[FEATURE_ON_OFF]:
            hk_state = current_state not in MEDIA_PLAYER_OFF_STATES
            _LOGGER.debug(
                '%s: Set current state for "on_off" to %s', self.entity_id, hk_state
            )
            on_off_char.set_value(hk_state)

        if play_pause_char := self.chars[FEATURE_PLAY_PAUSE]:
            hk_state = current_state == STATE_PLAYING
            _LOGGER.debug(
                '%s: Set current state for "play_pause" to %s',
                self.entity_id,
                hk_state,
            )
            play_pause_char.set_value(hk_state)

        if play_stop_char := self.chars[FEATURE_PLAY_STOP]:
            hk_state = current_state == STATE_PLAYING
            _LOGGER.debug(
                '%s: Set current state for "play_stop" to %s',
                self.entity_id,
                hk_state,
            )
            play_stop_char.set_value(hk_state)

        if toggle_mute_char := self.chars[FEATURE_TOGGLE_MUTE]:
            mute_state = bool(new_state.attributes.get(ATTR_MEDIA_VOLUME_MUTED))
            _LOGGER.debug(
                '%s: Set current state for "toggle_mute" to %s',
                self.entity_id,
                mute_state,
            )
            toggle_mute_char.set_value(mute_state)


@TYPES.register("TelevisionMediaPlayer")
class TelevisionMediaPlayer(RemoteInputSelectAccessory):
    """Generate a Television Media Player accessory."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize a Television Media Player accessory object."""
        super().__init__(
            MediaPlayerEntityFeature.SELECT_SOURCE,
            ATTR_INPUT_SOURCE,
            ATTR_INPUT_SOURCE_LIST,
            *args,
            **kwargs,
        )
        state = self.hass.states.get(self.entity_id)
        assert state
        features = state.attributes.get(ATTR_SUPPORTED_FEATURES, 0)

        self.chars_speaker: list[str] = []

        self._supports_play_pause = features & (
            MediaPlayerEntityFeature.PLAY | MediaPlayerEntityFeature.PAUSE
        )
        if (
            features & MediaPlayerEntityFeature.VOLUME_MUTE
            or features & MediaPlayerEntityFeature.VOLUME_STEP
        ):
            self.chars_speaker.extend(
                (CHAR_NAME, CHAR_ACTIVE, CHAR_VOLUME_CONTROL_TYPE, CHAR_VOLUME_SELECTOR)
            )
            if features & MediaPlayerEntityFeature.VOLUME_SET:
                self.chars_speaker.append(CHAR_VOLUME)

        if CHAR_VOLUME_SELECTOR in self.chars_speaker:
            serv_speaker = self.add_preload_service(
                SERV_TELEVISION_SPEAKER, self.chars_speaker
            )
            self.serv_tv.add_linked_service(serv_speaker)

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

        self.async_update_state(state)

    def set_on_off(self, value: bool) -> None:
        """Move switch state to value if call came from HomeKit."""
        _LOGGER.debug('%s: Set switch state for "on_off" to %s', self.entity_id, value)
        service = SERVICE_TURN_ON if value else SERVICE_TURN_OFF
        params = {ATTR_ENTITY_ID: self.entity_id}
        self.async_call_service(DOMAIN, service, params)

    def set_mute(self, value: bool) -> None:
        """Move switch state to value if call came from HomeKit."""
        _LOGGER.debug(
            '%s: Set switch state for "toggle_mute" to %s', self.entity_id, value
        )
        params = {ATTR_ENTITY_ID: self.entity_id, ATTR_MEDIA_VOLUME_MUTED: value}
        self.async_call_service(DOMAIN, SERVICE_VOLUME_MUTE, params)

    def set_volume(self, value: bool) -> None:
        """Send volume step value if call came from HomeKit."""
        _LOGGER.debug("%s: Set volume to %s", self.entity_id, value)
        params = {ATTR_ENTITY_ID: self.entity_id, ATTR_MEDIA_VOLUME_LEVEL: value}
        self.async_call_service(DOMAIN, SERVICE_VOLUME_SET, params)

    def set_volume_step(self, value: bool) -> None:
        """Send volume step value if call came from HomeKit."""
        _LOGGER.debug("%s: Step volume by %s", self.entity_id, value)
        service = SERVICE_VOLUME_DOWN if value else SERVICE_VOLUME_UP
        params = {ATTR_ENTITY_ID: self.entity_id}
        self.async_call_service(DOMAIN, service, params)

    def set_input_source(self, value: int) -> None:
        """Send input set value if call came from HomeKit."""
        _LOGGER.debug("%s: Set current input to %s", self.entity_id, value)
        source_name = self._mapped_sources[self.sources[value]]
        params = {ATTR_ENTITY_ID: self.entity_id, ATTR_INPUT_SOURCE: source_name}
        self.async_call_service(DOMAIN, SERVICE_SELECT_SOURCE, params)

    def set_remote_key(self, value: int) -> None:
        """Send remote key value if call came from HomeKit."""
        _LOGGER.debug("%s: Set remote key to %s", self.entity_id, value)
        if (key_name := REMOTE_KEYS.get(value)) is None:
            _LOGGER.warning("%s: Unhandled key press for %s", self.entity_id, value)
            return

        if key_name == KEY_PLAY_PAUSE and self._supports_play_pause:
            # Handle Play Pause by directly updating the media player entity.
            state_obj = self.hass.states.get(self.entity_id)
            assert state_obj
            state = state_obj.state
            if state in (STATE_PLAYING, STATE_PAUSED):
                service = (
                    SERVICE_MEDIA_PLAY if state == STATE_PAUSED else SERVICE_MEDIA_PAUSE
                )
            else:
                service = SERVICE_MEDIA_PLAY_PAUSE
            params = {ATTR_ENTITY_ID: self.entity_id}
            self.async_call_service(DOMAIN, service, params)
            return

        # Unhandled keys can be handled by listening to the event bus
        self.hass.bus.async_fire(
            EVENT_HOMEKIT_TV_REMOTE_KEY_PRESSED,
            {ATTR_KEY_NAME: key_name, ATTR_ENTITY_ID: self.entity_id},
        )

    @callback
    def async_update_state(self, new_state: State) -> None:
        """Update Television state after state changed."""
        current_state = new_state.state

        # Power state television
        hk_state = 0
        if current_state not in MEDIA_PLAYER_OFF_STATES:
            hk_state = 1
        _LOGGER.debug("%s: Set current active state to %s", self.entity_id, hk_state)
        self.char_active.set_value(hk_state)

        # Set mute state
        if CHAR_VOLUME_SELECTOR in self.chars_speaker:
            current_mute_state = bool(new_state.attributes.get(ATTR_MEDIA_VOLUME_MUTED))
            _LOGGER.debug(
                "%s: Set current mute state to %s",
                self.entity_id,
                current_mute_state,
            )
            self.char_mute.set_value(current_mute_state)

        self._async_update_input_state(hk_state, new_state)


@TYPES.register("ReceiverMediaPlayer")
class ReceiverMediaPlayer(TelevisionMediaPlayer):
    """Generate a Receiver Media Player accessory.

    For HomeKit, a Receiver Media Player is exactly the same as a
    Television Media Player except it has a different category
    which will tell HomeKit how to render the device.
    """

    def __init__(self, *args: Any) -> None:
        """Initialize a Receiver Media Player accessory object."""
        super().__init__(*args, category=CATEGORY_RECEIVER)
