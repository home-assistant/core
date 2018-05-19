"""Class to hold all media player accessories."""
import logging

from collections import namedtuple
from pyhap.const import CATEGORY_SWITCH

from homeassistant.const import (
    ATTR_ENTITY_ID, SERVICE_TURN_ON, SERVICE_TURN_OFF, STATE_ON, STATE_OFF,
    STATE_PLAYING, STATE_PAUSED, SERVICE_MEDIA_PLAY, SERVICE_MEDIA_PAUSE,
    STATE_IDLE, CONF_MODE, SERVICE_MEDIA_STOP, SERVICE_VOLUME_MUTE,
    STATE_UNKNOWN, CONF_NAME)
from homeassistant.components.media_player import (
    ATTR_MEDIA_VOLUME_MUTED, DOMAIN)

from . import TYPES
from .accessories import HomeAccessory
from .const import (
    SERV_SWITCH, CHAR_ON, ON_OFF, PLAY_PAUSE, PLAY_STOP, TOGGLE_MUTE,
    CHAR_NAME)

_LOGGER = logging.getLogger(__name__)

Mode = namedtuple('Mode',
                  ['on_state', 'off_state', 'on_service', 'off_service'])

DEFAULT_MODE_LIST = (ON_OFF, PLAY_PAUSE, PLAY_STOP, TOGGLE_MUTE)

STATE_SERVICE_MAP = {
    ON_OFF: Mode(STATE_ON, STATE_OFF, SERVICE_TURN_ON, SERVICE_TURN_OFF),
    PLAY_PAUSE: Mode(STATE_PLAYING, STATE_PAUSED, SERVICE_MEDIA_PLAY,
                     SERVICE_MEDIA_PAUSE),
    PLAY_STOP: Mode(STATE_PLAYING, STATE_IDLE, SERVICE_MEDIA_PLAY,
                    SERVICE_MEDIA_STOP),
    TOGGLE_MUTE: Mode(True, False, SERVICE_VOLUME_MUTE, SERVICE_VOLUME_MUTE)
}


@TYPES.register('MediaPlayer')
class MediaPlayer(HomeAccessory):
    """Generate a Media Player accessory."""

    def __init__(self, *args):
        """Initialize a Switch accessory object."""
        super().__init__(*args, category=CATEGORY_SWITCH)

        self.mode_list = self.config.get(CONF_MODE)
        self.name = self.config.get(CONF_NAME, self.entity_id)

        if ON_OFF in self.mode_list:
            self.on_off_flag_target_state = False
            serv_on_off = self.add_preload_service(SERV_SWITCH)
            serv_on_off.configure_char(
                CHAR_NAME, value='{}_{}'.format(self.name, ON_OFF))
            self.char_on_off = serv_on_off.configure_char(
                CHAR_ON, value=False, setter_callback=self.set_on_off)

        if PLAY_PAUSE in self.mode_list:
            self.play_pause_flag_target_state = False
            serv_play_pause = self.add_preload_service(SERV_SWITCH)
            serv_play_pause.configure_char(
                CHAR_NAME, value='{}_{}'.format(self.name, PLAY_PAUSE))
            self.char_play_pause = serv_play_pause.configure_char(
                CHAR_ON, value=False, setter_callback=self.set_play_pause)

        if PLAY_STOP in self.mode_list:
            self.play_stop_flag_target_state = False
            serv_play_stop = self.add_preload_service(SERV_SWITCH)
            serv_play_stop.configure_char(
                CHAR_NAME, value='{}_{}'.format(self.name, PLAY_STOP))
            self.char_play_stop = serv_play_stop.configure_char(
                CHAR_ON, value=False, setter_callback=self.set_play_stop)

        if TOGGLE_MUTE in self.mode_list:
            self.toggle_mute_flag_target_state = False
            serv_toggle_mute = self.add_preload_service(SERV_SWITCH)
            serv_toggle_mute.configure_char(
                CHAR_NAME, value='{}_{}'.format(self.name, TOGGLE_MUTE))
            self.char_toggle_mute = serv_toggle_mute.configure_char(
                CHAR_ON, value=False, setter_callback=self.set_toggle_mute)

    def set_on_off(self, value):
        """Move switch state to value if call came from HomeKit."""
        _LOGGER.debug('%s: Set switch state to %s', self.entity_id, value)
        self.on_off_flag_target_state = True
        service = SERVICE_TURN_ON if value else SERVICE_TURN_OFF
        params = {ATTR_ENTITY_ID: self.entity_id}
        self.hass.services.call(DOMAIN, service, params)

    def set_play_pause(self, value):
        """Move switch state to value if call came from HomeKit."""
        _LOGGER.debug('%s: Set switch state to %s', self.entity_id, value)
        self.play_pause_flag_target_state = True
        service = SERVICE_MEDIA_PLAY if value else SERVICE_MEDIA_PAUSE
        params = {ATTR_ENTITY_ID: self.entity_id}
        self.hass.services.call(DOMAIN, service, params)

    def set_play_stop(self, value):
        """Move switch state to value if call came from HomeKit."""
        _LOGGER.debug('%s: Set switch state to %s', self.entity_id, value)
        self.play_stop_flag_target_state = True
        service = SERVICE_MEDIA_PLAY if value else SERVICE_MEDIA_STOP
        params = {ATTR_ENTITY_ID: self.entity_id}
        self.hass.services.call(DOMAIN, service, params)

    def set_toggle_mute(self, value):
        """Move switch state to value if call came from HomeKit."""
        _LOGGER.debug('%s: Set switch state to %s', self.entity_id, value)
        self.toggle_mute_flag_target_state = True
        params = {ATTR_ENTITY_ID: self.entity_id,
                  ATTR_MEDIA_VOLUME_MUTED: value}
        self.hass.services.call(DOMAIN, SERVICE_VOLUME_MUTE, params)

    def update_state(self, new_state):
        """Update switch state after state changed."""
        current_state = new_state.state

        if self.char_on_off:
            hk_state = current_state not in [STATE_OFF, STATE_UNKNOWN, 'None']
            if not self.on_off_flag_target_state:
                _LOGGER.debug('%s: Set current state to %s',
                              self.entity_id, hk_state)
                self.char_on_off.set_value(hk_state)
            self.on_off_flag_target_state = False

        if self.char_play_pause:
            hk_state = current_state == STATE_PLAYING
            if not self.play_pause_flag_target_state:
                _LOGGER.debug('%s: Set current state to %s',
                              self.entity_id, hk_state)
                self.char_play_pause.set_value(hk_state)
            self.play_pause_flag_target_state = False

        if self.char_play_stop:
            hk_state = current_state == STATE_PLAYING
            if not self.play_stop_flag_target_state:
                _LOGGER.debug('%s: Set current state to %s',
                              self.entity_id, hk_state)
                self.char_play_stop.set_value(hk_state)
            self.play_stop_flag_target_state = False

        if self.char_toggle_mute:
            current_state = new_state.attributes.get(ATTR_MEDIA_VOLUME_MUTED)
            hk_state = current_state
            if not self.toggle_mute_flag_target_state:
                _LOGGER.debug('%s: Set current state to %s',
                              self.entity_id, hk_state)
                self.char_toggle_mute.set_value(hk_state)
            self.toggle_mute_flag_target_state = False
