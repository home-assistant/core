"""
Support for Cambridge Audio Network Audio Players (StreamMagic platform).

Example configuration.yaml entry:
media_player:
    platform: cambridgeaudio
    host: 192.168.x.y
    command_off: "OFF"
    name: "CA 851N"

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/media_player.cambridgeaudio/
"""
import logging
# pylint: disable=unused-import
import voluptuous as vol

from homeassistant.components.media_player import (
    SUPPORT_TURN_OFF, SUPPORT_TURN_ON,
    SUPPORT_PAUSE, SUPPORT_PLAY, SUPPORT_PREVIOUS_TRACK, SUPPORT_NEXT_TRACK,
    SUPPORT_STOP, SUPPORT_SEEK, SUPPORT_SHUFFLE_SET,
    SUPPORT_SELECT_SOURCE, SUPPORT_CLEAR_PLAYLIST,
    SUPPORT_VOLUME_SET, SUPPORT_VOLUME_MUTE, SUPPORT_VOLUME_STEP,
    MediaPlayerDevice, PLATFORM_SCHEMA, MEDIA_TYPE_MUSIC)

from homeassistant.const import (STATE_ON, STATE_OFF, STATE_UNKNOWN,
                                 STATE_PLAYING, STATE_PAUSED, STATE_IDLE,
                                 CONF_HOST, CONF_NAME, CONF_COMMAND_OFF)

import homeassistant.helpers.config_validation as cv
import homeassistant.util.dt as dt_util

REQUIREMENTS = ['stream_magic==0.16']
DOMAIN = 'cambridgeaudio'
_LOGGER = logging.getLogger(__name__)

CONF_SOURCES = 'sources'
DEFAULT_NAME = 'Cambridge Audio Streamer'
DEFAULT_PWROFF_CMD = 'OFF'
KNOWN_HOSTS = []

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_HOST): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_COMMAND_OFF, default=DEFAULT_PWROFF_CMD): cv.string
})

# supported features in all configurations
SUPPORT_CAMBRIDGE_COMMON = SUPPORT_TURN_OFF | SUPPORT_TURN_ON |\
                           SUPPORT_PLAY | SUPPORT_SELECT_SOURCE |\
                           SUPPORT_CLEAR_PLAYLIST | SUPPORT_STOP

# supported features when device is configured as pre-amp
SUPPORT_CAMBRIDGE_PREAMP = SUPPORT_VOLUME_MUTE | SUPPORT_VOLUME_SET |\
                           SUPPORT_VOLUME_STEP

# supported features for file-based media (i.e. not internet streams)
SUPPORT_CAMBRIDGE_FILEMEDIA = SUPPORT_SEEK | SUPPORT_PAUSE |\
                              SUPPORT_NEXT_TRACK | SUPPORT_PREVIOUS_TRACK |\
                              SUPPORT_SHUFFLE_SET


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Cambridge Audio platform."""
    from stream_magic import device as cadevice
    from stream_magic import discovery as ca

    host = config.get(CONF_HOST)
    name = config.get(CONF_NAME)

    if CONF_COMMAND_OFF in config:
        poweroff_command = config.get(CONF_COMMAND_OFF)
    else:
        poweroff_command = DEFAULT_PWROFF_CMD

    hosts = []
    sm = ca.StreamMagic()   # pylint: disable=C0103

    # found a new host that was specified in config file
    if CONF_HOST in config and host not in KNOWN_HOSTS:
        try:
            # discover() always returns a list, even for a single host
            devices = sm.discover(host=host)
            if devices:
                dev = devices[0]
                addr, port = dev[0][0:2]
                desc = dev[1]['server']
                scpd_url = dev[1]['location']
                if not name:
                    name = desc

                smdevice = cadevice.StreamMagicDevice(addr, port,
                                                      desc, scpd_url)
                hosts.append(CADevice(smdevice,
                                      config.get(CONF_SOURCES),
                                      poweroff_command,
                                      name=name))
                KNOWN_HOSTS.append(host)
                _LOGGER.debug("Added StreamMagic device with ip %s (%s)",
                              addr, desc)
        except OSError:
            _LOGGER.debug("Unable to connect to device at %s", host)
    else:
        # netdisco found the device
        if discovery_info is not None:
            addr = discovery_info.get('host')
            port = discovery_info.get('port')

            # if a name was set in the config, use it
            if name is None:
                name = discovery_info.get('name')

            scpd_url = discovery_info.get('ssdp_description')
            if addr not in KNOWN_HOSTS:
                smdevice = cadevice.StreamMagicDevice(addr, port,
                                                      name, scpd_url)
                hosts.append(CADevice(smdevice,
                                      config.get(CONF_SOURCES),
                                      poweroff_command,
                                      name=name))
                KNOWN_HOSTS.append(host)
                _LOGGER.debug("Added StreamMagic device with ip %s (%s)",
                              addr, name)
    add_devices(hosts, True)


class CADevice(MediaPlayerDevice):
    """Representation of a Cambridge Audio Network Audio Player device."""

    def __init__(self, smdevice, sources, poweroff_command, name=None):
        """Initialization."""
        self._smdevice = smdevice
        self._name = name
        self._pwstate = STATE_UNKNOWN
        self._state = STATE_UNKNOWN
        self._muted = False
        self._support_volumecontrol = self._smdevice.get_volume_control()
        self._volume = 0
        self._volume_max = self._smdevice.get_volume_max()
        self._source = None
        self._sources_map = dict((pr_num, pr_name)
                                 for pr_num, pr_name, pr_state
                                 in self._smdevice.get_preset_list())
        self._sources_reverse = {name: id for id, name
                                 in self._sources_map.items()}
        self._source_list = list(self._sources_map.values())
        self._audio_source = None
        self._power_off_cmd = poweroff_command.upper()  # IDLE or OFF
        self._artist = None
        self._album_art = None
        self._album = None
        self._trackno = None
        self._title = None
        self._duration = None
        self._position = None
        self._position_updated_at = None

    @property
    def name(self):
        """Return the name of the media_player."""
        return self._name

    @property
    def state(self):
        """Return the state of the media_player."""
        return self._state

    @property
    def is_volume_muted(self):
        """Return the state of the muting function."""
        return self._muted

    @property
    def source(self):
        """Return currently selected input source."""
        return self._audio_source

    @property
    def source_list(self):
        """Return a list of available Presets."""
        return self._source_list

    @property
    def supported_features(self):
        """Return supported features."""
        features = SUPPORT_CAMBRIDGE_COMMON
        if self._audio_source == "media player":
            features = features | SUPPORT_CAMBRIDGE_FILEMEDIA
        if self._support_volumecontrol:
            features = features | SUPPORT_CAMBRIDGE_PREAMP
        return features

    @property
    def media_content_type(self):
        """Return the media content type."""
        return MEDIA_TYPE_MUSIC

    @property
    def media_image_url(self):
        """Return image URI of current playing media."""
        return self._album_art

    @property
    def media_artist(self):
        """Return artist of current playing media."""
        return self._artist

    @property
    def media_album_name(self):
        """Return album of current playing media."""
        return self._album

    @property
    def media_track(self):
        """Return track number of current playing media."""
        return self._trackno

    @property
    def media_title(self):
        """Return title of current playing media."""
        return self._title

    @property
    def media_position(self):
        """Return position of current playing media in seconds."""
        if self._state is not STATE_PLAYING:
            return None
        return self._position

    @property
    def media_duration(self):
        """Return the duration of current playing media in seconds."""
        if self._state is not STATE_PLAYING:
            return None
        return self._duration

    @property
    def media_position_updated_at(self):
        """When was the position of the current playing media valid.

        Returns value from homeassistant.util.dt.utcnow().
        """
        if self._state in [STATE_PLAYING, STATE_PAUSED]:
            return self._position_updated_at

    @property
    def volume_level(self):
        """Current volume level (0..1)."""
        return float(self._volume) / float(self._volume_max)

    def clear_playlist(self):
        """Clear the playlist."""
        pass

    def media_next_track(self):
        """Skip to the next track, when in media player mode."""
        if self._audio_source == "media player":
            self._smdevice.trnsprt_next()
            self.schedule_update_ha_state()

    def media_previous_track(self):
        """Skip to the previous track, when in media player mode."""
        if self._audio_source == "media player":
            self._smdevice.trnsprt_prev()
            self.schedule_update_ha_state()

    def media_pause(self):
        """Pause playing the current media."""
        # there is no "pause" with internet radio streams
        if self._audio_source == "media player":
            self._smdevice.trnsprt_pause()
            self._state = STATE_PAUSED
        elif self._audio_source == "internet radio":
            self.media_stop()
            self._state = STATE_IDLE

    def media_seek(self, position):
        """Jump to the specified percent position within the current track."""
        abs_pos = round(self._to_seconds(self._duration) * (position/100), 2)
        abs_pos_h = int(abs_pos / 3600)
        abs_pos_m = int((abs_pos % 3600) / 60)
        abs_pos_s = int((abs_pos % 3600) % 60)
        abs_pos = '{:01d}:{:02d}:{:02d}'.format(abs_pos_h,
                                                abs_pos_m,
                                                abs_pos_s)
        self._smdevice.trnsprt_seek(abs_pos)

    def media_stop(self):
        """Stop playing the current media."""
        self._smdevice.trnsprt_stop()
        self._state = STATE_IDLE

    def media_play(self):
        """Start playing the current media."""
        self._smdevice.trnsprt_play()
        self._state = STATE_PLAYING

    def mute_volume(self, mute):
        """Mute the volume. This only works in pre-amp mode."""
        self._smdevice.volume_mute(mute)

    def play_media(self, media_type, media_id, **kwargs):
        """Play the specified media."""
        pass

    def select_source(self, source):
        """Switch to the selected internet radio preset."""
        self._smdevice.play_preset(self._sources_reverse[source])
        self.schedule_update_ha_state()

    def set_shuffle(self, shuffle):
        """Enable/disable shuffle play."""
        self._smdevice.set_shuffle(shuffle)

    def set_volume_level(self, volume):
        """Set the current volume level. This only works in pre-amp mode."""
        volume = int(float(self._volume_max) * float(volume))
        self._smdevice.set_volume(volume)

    def turn_off(self):
        """Switch the device OFF (default) or into IDLE mode."""
        _LOGGER.debug("Powering off (%s)", self._power_off_cmd)
        self._smdevice.power_off(power_state=self._power_off_cmd)
        self._pwstate = STATE_OFF

    def turn_on(self):
        """Turn the device on if it's in IDLE (network standby) mode."""
        if self._smdevice.get_power_state() == 'idle':
            self._smdevice.power_on()
            self._pwstate = STATE_ON

    @staticmethod
    def _to_seconds(timespec):
        """Helper function to translate a h:mm:ss time spec into seconds."""
        hours, minutes, seconds = timespec.split(':')
        return int(hours) * 60 + int(minutes) * 60 + int(seconds)

    def update(self):
        """Fetch new state data from the media_player."""
        dev = self._smdevice

        pwstate = dev.get_power_state()
        if pwstate is None or pwstate in ['idle', 'off']:
            self._pwstate = STATE_OFF
            self._state = STATE_OFF
            return
        self._pwstate = STATE_ON
        self._state = {
            'PLAYING': STATE_PLAYING,
            'PAUSED_PLAYBACK': STATE_PAUSED,
            'STOPPED': STATE_IDLE,
            'TRANSITIONING': STATE_PLAYING}.get(dev.get_transport_state())
        self._audio_source = dev.get_audio_source()

        try:
            self._source = dev.get_current_preset()['name']
        except TypeError:   # in case get_current_preset() returns None
            self._source = None

        # only need to update volume if the device supports changing it
        if self._support_volumecontrol:
            self._muted = dev.get_mute_state()
            self._volume = dev.get_volume()

        if self._state == STATE_PLAYING:
            if self._audio_source == "media player":
                self._album_art = dev.get_current_track_info()['albumArtURI']
                self._artist = dev.get_current_track_info()['artist']
                self._album = dev.get_current_track_info()['album']
                self._trackno = dev.get_current_track_info()['origTrackNo']
                self._title = dev.get_current_track_info()['trackTitle']

                # track position in seconds
                self._position = dev.get_current_track_info()['currentPos']
                self._position = self._to_seconds(self._position)
                # self._position = "{:.1f}".format(float(pos / tracklen * 100))

                # track length in seconds
                self._duration = dev.get_current_track_info()['trackLength']
                self._duration = self._to_seconds(self._duration)

                self._position_updated_at = dt_util.utcnow()

            elif self._audio_source == "internet radio":
                self._artist = dev.get_playback_details()['artist']
                self._album = dev.get_playback_details()['stream']
                self._album_art = None
                self._trackno = None
                self._title = None
