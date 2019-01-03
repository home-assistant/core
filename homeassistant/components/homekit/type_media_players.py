"""Class to hold all media player accessories."""
import logging

from pyhap.const import CATEGORY_SWITCH

from homeassistant.const import (
    ATTR_ENTITY_ID, SERVICE_MEDIA_PAUSE, SERVICE_MEDIA_PLAY,
    SERVICE_MEDIA_STOP, SERVICE_TURN_OFF, SERVICE_TURN_ON, SERVICE_VOLUME_MUTE,
    STATE_OFF, STATE_PLAYING, STATE_UNKNOWN)
from homeassistant.components.media_player import (
    ATTR_MEDIA_VOLUME_MUTED, DOMAIN)

from . import TYPES
from .accessories import HomeAccessory
from .const import (
    CHAR_NAME, CHAR_ON, CONF_FEATURE_LIST, FEATURE_ON_OFF, FEATURE_PLAY_PAUSE,
    FEATURE_PLAY_STOP, FEATURE_TOGGLE_MUTE, SERV_SWITCH)

_LOGGER = logging.getLogger(__name__)

MODE_FRIENDLY_NAME = {FEATURE_ON_OFF: 'Power',
                      FEATURE_PLAY_PAUSE: 'Play/Pause',
                      FEATURE_PLAY_STOP: 'Play/Stop',
                      FEATURE_TOGGLE_MUTE: 'Mute'}


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
