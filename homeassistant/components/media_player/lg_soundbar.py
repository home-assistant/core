"""
Support for LG soundbars.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/media_player.lg_soundbar/
"""
import logging

from homeassistant.components.media_player import (
    MediaPlayerDevice)
from homeassistant.components.media_player.const import (
    SUPPORT_SELECT_SOURCE, SUPPORT_VOLUME_MUTE, SUPPORT_VOLUME_SET,
    SUPPORT_SELECT_SOUND_MODE)

from homeassistant.const import STATE_ON

REQUIREMENTS = ['temescal==0.1']

_LOGGER = logging.getLogger(__name__)

SUPPORT_LG = SUPPORT_VOLUME_SET | SUPPORT_VOLUME_MUTE | SUPPORT_SELECT_SOURCE \
             | SUPPORT_SELECT_SOUND_MODE


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the LG platform."""
    if discovery_info is not None:
        add_entities([LGDevice(discovery_info)], True)


class LGDevice(MediaPlayerDevice):
    """Representation of an LG soundbar device."""

    def __init__(self, discovery_info):
        """Initialize the LG speakers."""
        import temescal

        host = discovery_info.get('host')
        port = discovery_info.get('port')

        self._name = ""
        self._volume = 0
        self._volume_min = 0
        self._volume_max = 0
        self._function = -1
        self._functions = []
        self._equaliser = -1
        self._equalisers = []
        self._mute = 0
        self._rear_volume = 0
        self._rear_volume_min = 0
        self._rear_volume_max = 0
        self._woofer_volume = 0
        self._woofer_volume_min = 0
        self._woofer_volume_max = 0
        self._bass = 0
        self._treble = 0

        self._device = temescal.temescal(host, port=port,
                                         callback=self.handle_event)
        self.update()

    def handle_event(self, response):
        """Handle responses from the speakers."""
        data = response['data']
        if response['msg'] == "EQ_VIEW_INFO":
            if 'i_bass' in data:
                self._bass = data['i_bass']
            if 'i_treble' in data:
                self._treble = data['i_treble']
            if 'ai_eq_list' in data:
                self._equalisers = data['ai_eq_list']
            if 'i_curr_eq' in data:
                self._equaliser = data['i_curr_eq']
        elif response['msg'] == "SPK_LIST_VIEW_INFO":
            if 'i_vol' in data:
                self._volume = data['i_vol']
            if 's_user_name' in data:
                self._name = data['s_user_name']
            if 'i_vol_min' in data:
                self._volume_min = data['i_vol_min']
            if 'i_vol_max' in data:
                self._volume_max = data['i_vol_max']
            if 'b_mute' in data:
                self._mute = data['b_mute']
            if 'i_curr_func' in data:
                self._function = data['i_curr_func']
        elif response['msg'] == "FUNC_VIEW_INFO":
            if 'i_curr_func' in data:
                self._function = data['i_curr_func']
            if 'ai_func_list' in data:
                self._functions = data['ai_func_list']
        elif response['msg'] == "SETTING_VIEW_INFO":
            if 'i_rear_min' in data:
                self._rear_volume_min = data['i_rear_min']
            if 'i_rear_max' in data:
                self._rear_volume_max = data['i_rear_max']
            if 'i_rear_level' in data:
                self._rear_volume = data['i_rear_level']
            if 'i_woofer_min' in data:
                self._woofer_volume_min = data['i_woofer_min']
            if 'i_woofer_max' in data:
                self._woofer_volume_max = data['i_woofer_max']
            if 'i_woofer_level' in data:
                self._woofer_volume = data['i_woofer_level']
            if 'i_curr_eq' in data:
                self._equaliser = data['i_curr_eq']
            if 's_user_name' in data:
                self._name = data['s_user_name']
        self.schedule_update_ha_state()

    def update(self):
        """Trigger updates from the device."""
        self._device.get_eq()
        self._device.get_info()
        self._device.get_func()
        self._device.get_settings()
        self._device.get_product_info()

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def volume_level(self):
        """Volume level of the media player (0..1)."""
        if self._volume_max != 0:
            return self._volume/self._volume_max
        return 0

    @property
    def is_volume_muted(self):
        """Boolean if volume is currently muted."""
        return self._mute

    @property
    def state(self):
        """Return the state of the device."""
        return STATE_ON

    @property
    def sound_mode(self):
        """Return the current sound mode."""
        import temescal
        if self._equaliser == -1:
            return ""
        return temescal.equalisers[self._equaliser]

    @property
    def sound_mode_list(self):
        """Return the available sound modes."""
        import temescal
        modes = []
        for equaliser in self._equalisers:
            modes.append(temescal.equalisers[equaliser])
        return sorted(modes)

    @property
    def source(self):
        """Return the current input source."""
        import temescal
        if self._function == -1:
            return ""
        return temescal.functions[self._function]

    @property
    def source_list(self):
        """List of available input sources."""
        import temescal
        sources = []
        for function in self._functions:
            sources.append(temescal.functions[function])
        return sorted(sources)

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        return SUPPORT_LG

    def set_volume_level(self, volume):
        """Set volume level, range 0..1."""
        volume = volume * self._volume_max
        self._device.set_volume(int(volume))

    def mute_volume(self, mute):
        """Mute (true) or unmute (false) media player."""
        self._device.set_mute(mute)

    def select_source(self, source):
        """Select input source."""
        import temescal
        self._device.set_func(temescal.functions.index(source))

    def select_sound_mode(self, sound_mode):
        """Set Sound Mode for Receiver.."""
        import temescal
        self._device.set_eq(temescal.equalisers.index(sound_mode))
