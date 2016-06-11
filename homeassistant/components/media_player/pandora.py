"""
Component for controlling Pandora stations through the pianobar client.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/media_player.pandora/
"""

import logging
import subprocess
import os
import signal
import re

from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.components.media_player import (
    SUPPORT_NEXT_TRACK, SUPPORT_PAUSE,
    SUPPORT_TURN_OFF, SUPPORT_TURN_ON,
    SUPPORT_SELECT_SOURCE, SERVICE_MEDIA_NEXT_TRACK, SERVICE_MEDIA_PLAY_PAUSE,
    SERVICE_MEDIA_PLAY, SERVICE_VOLUME_UP, SERVICE_VOLUME_DOWN,
    MediaPlayerDevice)
from homeassistant.const import STATE_OFF, STATE_PAUSED, STATE_PLAYING

REQUIREMENTS = ['pexpect==4.0.1']
_LOGGER = logging.getLogger(__name__)

# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the media player pandora platform."""
    pandora = PandoraMediaPlayer('Pandora')

    # make sure we end the pandora subprocess on exit in case user doesn't
    # power it down.
    def _stop_pianobar(_event):
        pandora.turn_off()

    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, _stop_pianobar)
    add_devices([pandora])

# SUPPORT_VOLUME_SET is close to available but we need volume up/down
# controls in the GUI.
PANDORA_SUPPORT = \
    SUPPORT_PAUSE | \
    SUPPORT_TURN_ON | SUPPORT_TURN_OFF | SUPPORT_NEXT_TRACK | \
    SUPPORT_SELECT_SOURCE


class PandoraMediaPlayer(MediaPlayerDevice):
    """A media player that uses the Pianobar interface to Pandora."""

    # We only implement the methods that we support
    # pylint: disable=abstract-method
    def __init__(self, name):
        """Initialize the demo device."""
        MediaPlayerDevice.__init__(self)
        self._name = name
        self._player_state = STATE_OFF
        self._pianobar_remote = PianobarRemote()

    @property
    def should_poll(self):
        """Push an update after each command."""
        return False

    @property
    def name(self):
        """Return the name of the media player."""
        return self._name

    @property
    def state(self):
        """Return the state of the player."""
        return self._player_state

    def turn_on(self):
        """Turn the media player on."""
        self._pianobar_remote.start()
        self._player_state = STATE_PLAYING
        self.update_ha_state()

    def turn_off(self):
        """Turn the media player off."""
        self._pianobar_remote.stop()
        self._player_state = STATE_OFF
        self.update_ha_state()

    def media_play(self):
        """Send play command."""
        self._pianobar_remote.send_service(SERVICE_MEDIA_PLAY_PAUSE)
        self._player_state = STATE_PLAYING
        self.update_ha_state()

    def media_pause(self):
        """Send pause command."""
        self._pianobar_remote.send_service(SERVICE_MEDIA_PLAY_PAUSE)
        self._player_state = STATE_PAUSED
        self.update_ha_state()

    def media_next_track(self):
        """Go to next track."""
        self._pianobar_remote.send_service(SERVICE_MEDIA_NEXT_TRACK)
        self.update_ha_state()

    @property
    def supported_media_commands(self):
        """Show what this supports."""
        return PANDORA_SUPPORT

    @property
    def source(self):
        """Name of the current input source."""
        return self._pianobar_remote.station

    @property
    def source_list(self):
        """List of available input sources."""
        self._pianobar_remote.get_stations()
        return self._pianobar_remote.stations

    def select_source(self, source):
        """Select input source."""
        self._pianobar_remote.set_station(source)

    @property
    def media_title(self):
        """Title of current playing media."""
        self._pianobar_remote.update_playing()
        return self._pianobar_remote.song

    @property
    def media_artist(self):
        """Artist of current playing media, music track only."""
        return self._pianobar_remote.artist

    @property
    def media_album_name(self):
        """Album name of current playing media, music track only."""
        return self._pianobar_remote.album


class PianobarRemote(object):
    """
    A light interface to the Pianobar remote control.

    pianobar has a FIFO remote control system that is challenging to
    get working if pianobar is in a subprocess. Using pexpect is more stable
    so this implementation uses pexpect.

    """
    CMD_MAP = {SERVICE_MEDIA_NEXT_TRACK: 'n',
               SERVICE_MEDIA_PLAY_PAUSE: 'p',
               SERVICE_MEDIA_PLAY: 'p',
               SERVICE_VOLUME_UP: ')',
               SERVICE_VOLUME_DOWN: '('}

    CURRENT_SONG_PATTERN = re.compile(r'"(.*?)"\s+by\s+"(.*?)"\son\s+"(.*?)"')
    STATION_PATTERN = re.compile('Station "(.+?)"')
    TIME_PATTERN = re.compile(rb'\d\d:\d\d')

    def __init__(self):
        """Construct a pianobar remote controller."""
        self._pianobar = None
        self.station = ''
        self.song = ''
        self.artist = ''
        self.album = ''
        self.stations = []

    def start(self):
        """Start the pianobar subprocess."""
        import pexpect
        self._pianobar = pexpect.spawn('sudo -u pi pianobar')
        _LOGGER.info('Started pianobar subprocess')

    def stop(self):
        """Stop the Pianobar subprocess."""
        if self._pianobar is None:
            _LOGGER.info('Pianobar subprocess already stopped')
            return
        self._pianobar.send('q')
        try:
            _LOGGER.info('Stopped Pianobar subprocess')
        except subprocess.TimeoutExpired:
            # kill the process group
            os.killpg(os.getpgid(self._pianobar.pid), signal.SIGTERM)
            _LOGGER.info('Killed Pianobar subprocess')
        self._pianobar = None

    def send_service(self, service_cmd):
        """Send a command to Pianobar."""
        command = self.CMD_MAP.get(service_cmd)
        if command is None:
            _LOGGER.info('Command %s not supported by Pianobar', service_cmd)
        self._pianobar.sendline(command)

    def update_playing(self):
        """Query pianobar for info about current song, station."""
        self._pianobar.send('i')
        self._pianobar.expect(self.TIME_PATTERN)
        response = self._pianobar.before.decode('utf-8')
        _LOGGER.info('PLAYING: ' + response)
        for line in response.split('\n'):
            station_match = re.search(self.STATION_PATTERN, line)
            if station_match:
                self.station = station_match.group(1)
                continue
            song_match = re.search(self.CURRENT_SONG_PATTERN, line)
            if song_match:
                self.song, self.artist, self.album = song_match.groups()
                _LOGGER.info('Got song as: %s', self.song)

    def get_stations(self):
        """List defined Pandora stations."""
        self._pianobar.send('s')
        self._pianobar.expect('[?]')
        station_lines = self._pianobar.before.decode('utf-8')
        _LOGGER.info(station_lines)
        self.stations = []
        for line in station_lines.split('\n'):
            match = re.search(r'\d+\).....(.+)', line)
            if match:
                self.stations.append(match.group(1))
        self._pianobar.sendcontrol('m')  # press enter with blank line

    def set_station(self, station):
        """Choose a different Pandora station and play it."""
        station_index = self.stations.index(station)
        self._pianobar.send('s')
        self._pianobar.expect('Select station')
        self._pianobar.sendline('{}'.format(station_index))
        self.update_playing()
