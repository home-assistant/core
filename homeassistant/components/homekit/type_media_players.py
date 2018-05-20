"""Class to hold all media player accessories."""
import logging

from pyhap.const import CATEGORY_SWITCH

from homeassistant.const import (
    ATTR_ENTITY_ID, SERVICE_TURN_ON, SERVICE_TURN_OFF, STATE_OFF,
    STATE_PLAYING, SERVICE_MEDIA_PLAY, SERVICE_MEDIA_PAUSE,
    CONF_MODE, SERVICE_MEDIA_STOP, SERVICE_VOLUME_MUTE, STATE_UNKNOWN)
from homeassistant.components.media_player import (
    ATTR_MEDIA_VOLUME_MUTED, DOMAIN)

from . import TYPES
from .accessories import HomeAccessory
from .const import (
    SERV_SWITCH, CHAR_ON, ON_OFF, PLAY_PAUSE, PLAY_STOP, TOGGLE_MUTE,
    CHAR_NAME)

_LOGGER = logging.getLogger(__name__)

MODE_FRIENDLY_NAME = {ON_OFF: 'Power',
                      PLAY_PAUSE: 'Play/Pause',
                      PLAY_STOP: 'Play/Stop',
                      TOGGLE_MUTE: 'Mute'}


@TYPES.register('MediaPlayer')
class MediaPlayer(HomeAccessory):
    """Generate a Media Player accessory."""

    def __init__(self, *args):
        """Initialize a Switch accessory object."""
        super().__init__(*args, category=CATEGORY_SWITCH)
        self.on_off_flag_target_state = False
        self.play_pause_flag_target_state = False
        self.play_stop_flag_target_state = False
        self.toggle_mute_flag_target_state = False

        self.char_on_off = None
        self.char_play_pause = None
        self.char_play_stop = None
        self.char_toggle_mute = None

        self.mode_list = self.config.get(CONF_MODE)

        if ON_OFF in self.mode_list:
            serv_on_off = self.add_preload_service(
                SERV_SWITCH, chars=CHAR_NAME)
            serv_on_off.configure_char(
                CHAR_NAME, value=self.generate_service_name(ON_OFF))
            self.char_on_off = serv_on_off.configure_char(
                CHAR_ON, value=False, setter_callback=self.set_on_off)

        if PLAY_PAUSE in self.mode_list:
            serv_play_pause = self.add_preload_service(
                SERV_SWITCH, chars=CHAR_NAME)
            serv_play_pause.configure_char(
                CHAR_NAME, value=self.generate_service_name(PLAY_PAUSE))
            self.char_play_pause = serv_play_pause.configure_char(
                CHAR_ON, value=False, setter_callback=self.set_play_pause)

        if PLAY_STOP in self.mode_list:
            serv_play_stop = self.add_preload_service(
                SERV_SWITCH, chars=CHAR_NAME)
            serv_play_stop.configure_char(
                CHAR_NAME, value=self.generate_service_name(PLAY_STOP))
            self.char_play_stop = serv_play_stop.configure_char(
                CHAR_ON, value=False, setter_callback=self.set_play_stop)

        if TOGGLE_MUTE in self.mode_list:
            serv_toggle_mute = self.add_preload_service(
                SERV_SWITCH, chars=CHAR_NAME)
            serv_toggle_mute.configure_char(
                CHAR_NAME, value=self.generate_service_name(TOGGLE_MUTE))
            self.char_toggle_mute = serv_toggle_mute.configure_char(
                CHAR_ON, value=False, setter_callback=self.set_toggle_mute)

    def generate_service_name(self, mode):
        """Generate name for individual service."""
        return '{} {}'.format(self.name, MODE_FRIENDLY_NAME[mode])

    def set_on_off(self, value):
        """Move switch state to value if call came from HomeKit."""
        _LOGGER.debug('%s: Set switch state for "on_off" to %s',
                      self.entity_id, value)
        self.on_off_flag_target_state = True
        service = SERVICE_TURN_ON if value else SERVICE_TURN_OFF
        params = {ATTR_ENTITY_ID: self.entity_id}
        self.hass.services.call(DOMAIN, service, params)

    def set_play_pause(self, value):
        """Move switch state to value if call came from HomeKit."""
        _LOGGER.debug('%s: Set switch state for "play_pause" to %s',
                      self.entity_id, value)
        self.play_pause_flag_target_state = True
        service = SERVICE_MEDIA_PLAY if value else SERVICE_MEDIA_PAUSE
        params = {ATTR_ENTITY_ID: self.entity_id}
        self.hass.services.call(DOMAIN, service, params)

    def set_play_stop(self, value):
        """Move switch state to value if call came from HomeKit."""
        _LOGGER.debug('%s: Set switch state for "play_stop" to %s',
                      self.entity_id, value)
        self.play_stop_flag_target_state = True
        service = SERVICE_MEDIA_PLAY if value else SERVICE_MEDIA_STOP
        params = {ATTR_ENTITY_ID: self.entity_id}
        self.hass.services.call(DOMAIN, service, params)

    def set_toggle_mute(self, value):
        """Move switch state to value if call came from HomeKit."""
        _LOGGER.debug('%s: Set switch state for "toggle_mute" to %s',
                      self.entity_id, value)
        self.toggle_mute_flag_target_state = True
        params = {ATTR_ENTITY_ID: self.entity_id,
                  ATTR_MEDIA_VOLUME_MUTED: value}
        self.hass.services.call(DOMAIN, SERVICE_VOLUME_MUTE, params)

    def update_state(self, new_state):
        """Update switch state after state changed."""
        current_state = new_state.state

        if self.char_on_off:
            hk_state = current_state \
                not in [STATE_OFF, STATE_UNKNOWN, 'None']
            if not self.on_off_flag_target_state:
                _LOGGER.debug('%s: Set current state for "on_off" to %s',
                              self.entity_id, hk_state)
                self.char_on_off.set_value(hk_state)
            self.on_off_flag_target_state = False

        if self.char_play_pause:
            hk_state = current_state == STATE_PLAYING
            if not self.play_pause_flag_target_state:
                _LOGGER.debug('%s: Set current state for "play_pause" to %s',
                              self.entity_id, hk_state)
                self.char_play_pause.set_value(hk_state)
            self.play_pause_flag_target_state = False

        if self.char_play_stop:
            hk_state = current_state == STATE_PLAYING
            if not self.play_stop_flag_target_state:
                _LOGGER.debug('%s: Set current state for "play_stop" to %s',
                              self.entity_id, hk_state)
                self.char_play_stop.set_value(hk_state)
            self.play_stop_flag_target_state = False

        if self.char_toggle_mute:
            current_state = new_state.attributes.get(ATTR_MEDIA_VOLUME_MUTED)
            hk_state = current_state
            if not self.toggle_mute_flag_target_state:
                _LOGGER.debug('%s: Set current state for "toggle_mute" to %s',
                              self.entity_id, hk_state)
                self.char_toggle_mute.set_value(hk_state)
            self.toggle_mute_flag_target_state = False
