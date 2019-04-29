"""Class to hold all media player accessories."""
import logging

from pyhap.const import CATEGORY_SWITCH, CATEGORY_TELEVISION

from homeassistant.components.media_player import (
    ATTR_INPUT_SOURCE, ATTR_MEDIA_VOLUME_MUTED, SERVICE_SELECT_SOURCE, DOMAIN)
from homeassistant.const import (
    ATTR_ENTITY_ID, SERVICE_MEDIA_PAUSE, SERVICE_MEDIA_PLAY,
    SERVICE_MEDIA_PLAY_PAUSE, SERVICE_MEDIA_STOP, SERVICE_TURN_OFF,
    SERVICE_TURN_ON, SERVICE_VOLUME_MUTE, SERVICE_VOLUME_UP,
    SERVICE_VOLUME_DOWN, STATE_OFF, STATE_PLAYING, STATE_PAUSED,
    STATE_UNKNOWN)

from . import TYPES
from .accessories import HomeAccessory
from .const import (
    CHAR_ACTIVE, CHAR_ACTIVE_IDENTIFIER, CHAR_CONFIGURED_NAME,
    CHAR_CURRENT_VISIBILITY_STATE, CHAR_IDENTIFIER, CHAR_INPUT_SOURCE_TYPE,
    CHAR_IS_CONFIGURED, CHAR_NAME, CHAR_SLEEP_DISCOVER_MODE,
    CHAR_MUTE, CHAR_ON, CHAR_REMOTE_KEY, CHAR_VOLUME_CONTROL_TYPE,
    CHAR_VOLUME_SELECTOR, CHAR_VOLUME, CONF_FEATURE_LIST, FEATURE_ON_OFF,
    FEATURE_PLAY_PAUSE, FEATURE_PLAY_STOP, FEATURE_SELECT_SOURCE,
    FEATURE_TOGGLE_MUTE, FEATURE_VOLUME_STEP, SERV_SWITCH, SERV_TELEVISION,
    SERV_TELEVISION_SPEAKER, SERV_INPUT_SOURCE)

_LOGGER = logging.getLogger(__name__)

REMOTE_KEYS = {
    0: "Rewind",
    1: "FastForward",
    2: "NextTrack",
    3: "PreviousTrack",
    4: "ArrowUp",
    5: "ArrowDown",
    6: "ArrowLeft",
    7: "ArrowRight",
    8: "Select",
    9: "Back",
    10: "Exit",
    15: "Information"
}

MEDIA_PLAYER_KEYS = {
    11: SERVICE_MEDIA_PLAY_PAUSE,
}


MODE_FRIENDLY_NAME = {
    FEATURE_ON_OFF: 'Power',
    FEATURE_PLAY_PAUSE: 'Play/Pause',
    FEATURE_PLAY_STOP: 'Play/Stop',
    FEATURE_TOGGLE_MUTE: 'Mute',
}


@TYPES.register('MediaPlayer')
class MediaPlayer(HomeAccessory):
    """Generate a Media Player accessory."""

    def __init__(self, *args):
        """Initialize a Switch accessory object."""
        super().__init__(*args, category=CATEGORY_SWITCH)
        self._flag = {FEATURE_ON_OFF: False, FEATURE_PLAY_PAUSE: False,
                      FEATURE_PLAY_STOP: False, FEATURE_TOGGLE_MUTE: False}
        self.chars = {FEATURE_ON_OFF: None, FEATURE_PLAY_PAUSE: None,
                      FEATURE_PLAY_STOP: None, FEATURE_TOGGLE_MUTE: None}
        feature_list = self.config[CONF_FEATURE_LIST]

        if FEATURE_ON_OFF in feature_list:
            name = self.generate_service_name(FEATURE_ON_OFF)
            serv_on_off = self.add_preload_service(SERV_SWITCH, CHAR_NAME)
            serv_on_off.configure_char(CHAR_NAME, value=name)
            self.chars[FEATURE_ON_OFF] = serv_on_off.configure_char(
                CHAR_ON, value=False, setter_callback=self.set_on_off)

        if FEATURE_PLAY_PAUSE in feature_list:
            name = self.generate_service_name(FEATURE_PLAY_PAUSE)
            serv_play_pause = self.add_preload_service(SERV_SWITCH, CHAR_NAME)
            serv_play_pause.configure_char(CHAR_NAME, value=name)
            self.chars[FEATURE_PLAY_PAUSE] = serv_play_pause.configure_char(
                CHAR_ON, value=False, setter_callback=self.set_play_pause)

        if FEATURE_PLAY_STOP in feature_list:
            name = self.generate_service_name(FEATURE_PLAY_STOP)
            serv_play_stop = self.add_preload_service(SERV_SWITCH, CHAR_NAME)
            serv_play_stop.configure_char(CHAR_NAME, value=name)
            self.chars[FEATURE_PLAY_STOP] = serv_play_stop.configure_char(
                CHAR_ON, value=False, setter_callback=self.set_play_stop)

        if FEATURE_TOGGLE_MUTE in feature_list:
            name = self.generate_service_name(FEATURE_TOGGLE_MUTE)
            serv_toggle_mute = self.add_preload_service(SERV_SWITCH, CHAR_NAME)
            serv_toggle_mute.configure_char(CHAR_NAME, value=name)
            self.chars[FEATURE_TOGGLE_MUTE] = serv_toggle_mute.configure_char(
                CHAR_ON, value=False, setter_callback=self.set_toggle_mute)

    def generate_service_name(self, mode):
        """Generate name for individual service."""
        return '{} {}'.format(self.display_name, MODE_FRIENDLY_NAME[mode])

    def set_on_off(self, value):
        """Move switch state to value if call came from HomeKit."""
        _LOGGER.debug('%s: Set switch state for "on_off" to %s',
                      self.entity_id, value)
        self._flag[FEATURE_ON_OFF] = True
        service = SERVICE_TURN_ON if value else SERVICE_TURN_OFF
        params = {ATTR_ENTITY_ID: self.entity_id}
        self.call_service(DOMAIN, service, params)

    def set_play_pause(self, value):
        """Move switch state to value if call came from HomeKit."""
        _LOGGER.debug('%s: Set switch state for "play_pause" to %s',
                      self.entity_id, value)
        self._flag[FEATURE_PLAY_PAUSE] = True
        service = SERVICE_MEDIA_PLAY if value else SERVICE_MEDIA_PAUSE
        params = {ATTR_ENTITY_ID: self.entity_id}
        self.call_service(DOMAIN, service, params)

    def set_play_stop(self, value):
        """Move switch state to value if call came from HomeKit."""
        _LOGGER.debug('%s: Set switch state for "play_stop" to %s',
                      self.entity_id, value)
        self._flag[FEATURE_PLAY_STOP] = True
        service = SERVICE_MEDIA_PLAY if value else SERVICE_MEDIA_STOP
        params = {ATTR_ENTITY_ID: self.entity_id}
        self.call_service(DOMAIN, service, params)

    def set_toggle_mute(self, value):
        """Move switch state to value if call came from HomeKit."""
        _LOGGER.debug('%s: Set switch state for "toggle_mute" to %s',
                      self.entity_id, value)
        self._flag[FEATURE_TOGGLE_MUTE] = True
        params = {ATTR_ENTITY_ID: self.entity_id,
                  ATTR_MEDIA_VOLUME_MUTED: value}
        self.call_service(DOMAIN, SERVICE_VOLUME_MUTE, params)

    def update_state(self, new_state):
        """Update switch state after state changed."""
        current_state = new_state.state

        if self.chars[FEATURE_ON_OFF]:
            hk_state = current_state not in (STATE_OFF, STATE_UNKNOWN, 'None')
            if not self._flag[FEATURE_ON_OFF]:
                _LOGGER.debug('%s: Set current state for "on_off" to %s',
                              self.entity_id, hk_state)
                self.chars[FEATURE_ON_OFF].set_value(hk_state)
            self._flag[FEATURE_ON_OFF] = False

        if self.chars[FEATURE_PLAY_PAUSE]:
            hk_state = current_state == STATE_PLAYING
            if not self._flag[FEATURE_PLAY_PAUSE]:
                _LOGGER.debug('%s: Set current state for "play_pause" to %s',
                              self.entity_id, hk_state)
                self.chars[FEATURE_PLAY_PAUSE].set_value(hk_state)
            self._flag[FEATURE_PLAY_PAUSE] = False

        if self.chars[FEATURE_PLAY_STOP]:
            hk_state = current_state == STATE_PLAYING
            if not self._flag[FEATURE_PLAY_STOP]:
                _LOGGER.debug('%s: Set current state for "play_stop" to %s',
                              self.entity_id, hk_state)
                self.chars[FEATURE_PLAY_STOP].set_value(hk_state)
            self._flag[FEATURE_PLAY_STOP] = False

        if self.chars[FEATURE_TOGGLE_MUTE]:
            current_state = new_state.attributes.get(ATTR_MEDIA_VOLUME_MUTED)
            if not self._flag[FEATURE_TOGGLE_MUTE]:
                _LOGGER.debug('%s: Set current state for "toggle_mute" to %s',
                              self.entity_id, current_state)
                self.chars[FEATURE_TOGGLE_MUTE].set_value(current_state)
            self._flag[FEATURE_TOGGLE_MUTE] = False


@TYPES.register('TelevisionMediaPlayer')
class TelevisionMediaPlayer(HomeAccessory):
    """Generate a Television Media Player accessory."""

    def __init__(self, *args):
        """Initialize a Switch accessory object."""
        super().__init__(*args, category=CATEGORY_SWITCH)
        self._flag = {FEATURE_ON_OFF: False, FEATURE_PLAY_PAUSE: False,
                      FEATURE_TOGGLE_MUTE: False, FEATURE_SELECT_SOURCE: False}
        self.chars = {FEATURE_ON_OFF: None, FEATURE_PLAY_PAUSE: None,
                      FEATURE_TOGGLE_MUTE: None, FEATURE_SELECT_SOURCE: None,
                      FEATURE_VOLUME_STEP: None}

        self.sources = []

        self.category = CATEGORY_TELEVISION
        television = self.add_preload_service(SERV_TELEVISION,
                                              [CHAR_REMOTE_KEY])
        television.configure_char(CHAR_CONFIGURED_NAME,
                                  value=self.display_name)
        television.configure_char(CHAR_SLEEP_DISCOVER_MODE, value=True)
        self.chars[FEATURE_ON_OFF] = television.configure_char(
            CHAR_ACTIVE, setter_callback=self.set_on_off)

        self.chars[FEATURE_PLAY_PAUSE] = television.configure_char(
            CHAR_REMOTE_KEY, setter_callback=self.set_remote_key)

        television_speaker = self.add_preload_service(
            SERV_TELEVISION_SPEAKER, [CHAR_NAME, CHAR_ACTIVE,
                                      CHAR_VOLUME_CONTROL_TYPE,
                                      CHAR_VOLUME_SELECTOR, CHAR_VOLUME])
        television.add_linked_service(television_speaker)

        name = '{} {}'.format(self.display_name, 'Volume')
        television_speaker.configure_char(CHAR_NAME, value=name)
        television_speaker.configure_char(CHAR_ACTIVE, value=1)

        self.chars[FEATURE_TOGGLE_MUTE] = television_speaker.configure_char(
            CHAR_MUTE, value=False,
            setter_callback=self.set_toggle_mute)

        television_speaker.configure_char(CHAR_VOLUME_CONTROL_TYPE, value=1)
        self.chars[FEATURE_VOLUME_STEP] = television_speaker.configure_char(
            CHAR_VOLUME_SELECTOR, setter_callback=self.set_volume_step)

        self.chars[FEATURE_SELECT_SOURCE] = television.configure_char(
            CHAR_ACTIVE_IDENTIFIER, setter_callback=self.set_input_source)

        self.sources = self.hass.states.get(
            self.entity_id).attributes.get('source_list')
        if self.sources:
            for index, source in enumerate(self.sources):
                input_service = self.add_preload_service(SERV_INPUT_SOURCE, [
                    CHAR_IDENTIFIER, CHAR_NAME])

                input_service.configure_char(
                    CHAR_CONFIGURED_NAME, value=source)
                input_service.configure_char(CHAR_NAME, value=source)
                input_service.configure_char(
                    CHAR_IDENTIFIER, value=index)
                input_service.configure_char(
                    CHAR_IS_CONFIGURED, value=True)
                input_type = 3 if "hdmi" in source.lower() else 0
                input_service.configure_char(CHAR_INPUT_SOURCE_TYPE,
                                             value=input_type)
                input_service.configure_char(
                    CHAR_CURRENT_VISIBILITY_STATE, value=False)
                television.add_linked_service(input_service)
                _LOGGER.debug('%s: Added source %s.', self.entity_id,
                              source)

        self.set_primary_service(television)

    def set_on_off(self, value):
        """Move switch state to value if call came from HomeKit."""
        _LOGGER.debug('%s: Set switch state for "on_off" to %s',
                      self.entity_id, value)
        self._flag[FEATURE_ON_OFF] = True
        service = SERVICE_TURN_ON if value else SERVICE_TURN_OFF
        params = {ATTR_ENTITY_ID: self.entity_id}
        self.call_service(DOMAIN, service, params)

    def set_play_pause(self, value):
        """Move switch state to value if call came from HomeKit."""
        _LOGGER.debug('%s: Set switch state for "play_pause" to %s',
                      self.entity_id, value)
        self._flag[FEATURE_PLAY_PAUSE] = True
        service = SERVICE_MEDIA_PLAY if value else SERVICE_MEDIA_PAUSE
        params = {ATTR_ENTITY_ID: self.entity_id}
        self.call_service(DOMAIN, service, params)

    def set_toggle_mute(self, value):
        """Move switch state to value if call came from HomeKit."""
        _LOGGER.debug('%s: Set switch state for "toggle_mute" to %s',
                      self.entity_id, value)
        self._flag[FEATURE_TOGGLE_MUTE] = True
        params = {ATTR_ENTITY_ID: self.entity_id,
                  ATTR_MEDIA_VOLUME_MUTED: value}
        self.call_service(DOMAIN, SERVICE_VOLUME_MUTE, params)

    def set_volume_step(self, value):
        """Send volume step value if call came from HomeKit."""
        _LOGGER.debug('%s: Step tv_volume for "tv_volume" to %s',
                      self.entity_id, value)

        service = SERVICE_VOLUME_DOWN if value else SERVICE_VOLUME_UP
        params = {ATTR_ENTITY_ID: self.entity_id}
        self.call_service(DOMAIN, service, params)

    def set_input_source(self, value):
        """Send input set value if call came from HomeKit."""
        _LOGGER.debug('%s: Set select_source for "select_source" to %s',
                      self.entity_id, value)

        source = self.sources[value]
        self._flag[FEATURE_SELECT_SOURCE] = True
        params = {ATTR_ENTITY_ID: self.entity_id,
                  ATTR_INPUT_SOURCE: source}
        self.call_service(DOMAIN, SERVICE_SELECT_SOURCE, params)

    def set_remote_key(self, value):
        """Send remote key value if call came from HomeKit."""
        _LOGGER.debug('%s: Set remote key for "play_pause" to %s',
                      self.entity_id, value)

        if value in MEDIA_PLAYER_KEYS:
            service = MEDIA_PLAYER_KEYS[value]
            if service == SERVICE_MEDIA_PLAY_PAUSE:
                state = self.hass.states.get(self.entity_id).state
                if state in (STATE_PLAYING, STATE_PAUSED):
                    self.set_play_pause(state == STATE_PAUSED)
                    return
            params = {ATTR_ENTITY_ID: self.entity_id}
            self.call_service(DOMAIN, service, params)

    def update_state(self, new_state):
        """Update switch state after state changed."""
        current_state = new_state.state

        if self.chars[FEATURE_ON_OFF]:
            hk_state = current_state not in (STATE_OFF, STATE_UNKNOWN, 'None')
            if not self._flag[FEATURE_ON_OFF]:
                if self.category is CATEGORY_TELEVISION:
                    hk_state = 1 if hk_state else 0
                _LOGGER.debug('%s: Set current state for "on_off" to %s',
                              self.entity_id, hk_state)
                self.chars[FEATURE_ON_OFF].set_value(hk_state)
            self._flag[FEATURE_ON_OFF] = False

        if self.chars[FEATURE_PLAY_PAUSE]:
            hk_state = current_state == STATE_PLAYING
            if not self._flag[FEATURE_PLAY_PAUSE] and \
                    not self.category == CATEGORY_TELEVISION:
                _LOGGER.debug('%s: Set current state for "play_pause" to %s',
                              self.entity_id, hk_state)
                self.chars[FEATURE_PLAY_PAUSE].set_value(hk_state)
            self._flag[FEATURE_PLAY_PAUSE] = False

        if self.chars[FEATURE_TOGGLE_MUTE]:
            current_state = new_state.attributes.get(ATTR_MEDIA_VOLUME_MUTED)
            if not self._flag[FEATURE_TOGGLE_MUTE]:
                _LOGGER.debug('%s: Set current state for "toggle_mute" to %s',
                              self.entity_id, current_state)
                self.chars[FEATURE_TOGGLE_MUTE].set_value(current_state)
            self._flag[FEATURE_TOGGLE_MUTE] = False

        if self.chars[FEATURE_SELECT_SOURCE]:
            source_name = new_state.attributes.get(ATTR_INPUT_SOURCE)
            if self.sources and not self._flag[FEATURE_SELECT_SOURCE]:
                _LOGGER.debug(
                    '%s: Set current state for "select_source" to %s',
                    self.entity_id, source_name)
                if source_name in self.sources:
                    index = self.sources.index(source_name)
                    self.chars[FEATURE_SELECT_SOURCE].set_value(index)
                else:
                    self.chars[FEATURE_SELECT_SOURCE].set_value(0)
            self._flag[FEATURE_SELECT_SOURCE] = False
