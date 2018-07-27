"""
Component for controlling Pandora stations through the pianobar client.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/media_player.pandora/
"""
import logging
import re
import os
import signal
from datetime import timedelta
import shutil

from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.components.media_player import (
    SUPPORT_NEXT_TRACK, SUPPORT_PAUSE, MEDIA_TYPE_MUSIC,
    SUPPORT_TURN_OFF, SUPPORT_TURN_ON, SUPPORT_PLAY,
    SUPPORT_SELECT_SOURCE, SERVICE_MEDIA_NEXT_TRACK, SERVICE_MEDIA_PLAY_PAUSE,
    SERVICE_MEDIA_PLAY, SERVICE_VOLUME_UP, SERVICE_VOLUME_DOWN,
    MediaPlayerDevice)
from homeassistant.const import (STATE_OFF, STATE_PAUSED, STATE_PLAYING,
                                 STATE_IDLE)
from homeassistant import util

REQUIREMENTS = ['pexpect==4.6.0']
_LOGGER = logging.getLogger(__name__)

# SUPPORT_VOLUME_SET is close to available but we need volume up/down
# controls in the GUI.
PANDORA_SUPPORT = \
    SUPPORT_PAUSE | \
    SUPPORT_TURN_ON | SUPPORT_TURN_OFF | SUPPORT_NEXT_TRACK | \
    SUPPORT_SELECT_SOURCE | SUPPORT_PLAY

CMD_MAP = {SERVICE_MEDIA_NEXT_TRACK: 'n',
           SERVICE_MEDIA_PLAY_PAUSE: 'p',
           SERVICE_MEDIA_PLAY: 'p',
           SERVICE_VOLUME_UP: ')',
           SERVICE_VOLUME_DOWN: '('}
MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=2)
CURRENT_SONG_PATTERN = re.compile(r'"(.*?)"\s+by\s+"(.*?)"\son\s+"(.*?)"',
                                  re.MULTILINE)
STATION_PATTERN = re.compile(r'Station\s"(.+?)"', re.MULTILINE)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Pandora media player platform."""
    if not _pianobar_exists():
        return False
    pandora = PandoraMediaPlayer('Pandora')

    # Make sure we end the pandora subprocess on exit in case user doesn't
    # power it down.
    def _stop_pianobar(_event):
        pandora.turn_off()

    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, _stop_pianobar)
    add_devices([pandora])


class PandoraMediaPlayer(MediaPlayerDevice):
    """A media player that uses the Pianobar interface to Pandora."""

    def __init__(self, name):
        """Initialize the Pandora device."""
        MediaPlayerDevice.__init__(self)
        self._name = name
        self._player_state = STATE_OFF
        self._station = ''
        self._media_title = ''
        self._media_artist = ''
        self._media_album = ''
        self._stations = []
        self._time_remaining = 0
        self._media_duration = 0
        self._pianobar = None

    @property
    def should_poll(self):
        """Return the polling state."""
        return True

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
        import pexpect
        if self._player_state != STATE_OFF:
            return
        self._pianobar = pexpect.spawn('pianobar')
        _LOGGER.info("Started pianobar subprocess")
        mode = self._pianobar.expect(['Receiving new playlist',
                                      'Select station:',
                                      'Email:'])
        if mode == 1:
            # station list was presented. dismiss it.
            self._pianobar.sendcontrol('m')
        elif mode == 2:
            _LOGGER.warning(
                "The pianobar client is not configured to log in. "
                "Please create a config file for it as described at "
                "https://home-assistant.io/components/media_player.pandora/")
            # pass through the email/password prompts to quit cleanly
            self._pianobar.sendcontrol('m')
            self._pianobar.sendcontrol('m')
            self._pianobar.terminate()
            self._pianobar = None
            return
        self._update_stations()
        self.update_playing_status()

        self._player_state = STATE_IDLE
        self.schedule_update_ha_state()

    def turn_off(self):
        """Turn the media player off."""
        import pexpect
        if self._pianobar is None:
            _LOGGER.info("Pianobar subprocess already stopped")
            return
        self._pianobar.send('q')
        try:
            _LOGGER.debug("Stopped Pianobar subprocess")
            self._pianobar.terminate()
        except pexpect.exceptions.TIMEOUT:
            # kill the process group
            os.killpg(os.getpgid(self._pianobar.pid), signal.SIGTERM)
            _LOGGER.debug("Killed Pianobar subprocess")
        self._pianobar = None
        self._player_state = STATE_OFF
        self.schedule_update_ha_state()

    def media_play(self):
        """Send play command."""
        self._send_pianobar_command(SERVICE_MEDIA_PLAY_PAUSE)
        self._player_state = STATE_PLAYING
        self.schedule_update_ha_state()

    def media_pause(self):
        """Send pause command."""
        self._send_pianobar_command(SERVICE_MEDIA_PLAY_PAUSE)
        self._player_state = STATE_PAUSED
        self.schedule_update_ha_state()

    def media_next_track(self):
        """Go to next track."""
        self._send_pianobar_command(SERVICE_MEDIA_NEXT_TRACK)
        self.schedule_update_ha_state()

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        return PANDORA_SUPPORT

    @property
    def source(self):
        """Name of the current input source."""
        return self._station

    @property
    def source_list(self):
        """List of available input sources."""
        return self._stations

    @property
    def media_title(self):
        """Title of current playing media."""
        self.update_playing_status()
        return self._media_title

    @property
    def media_content_type(self):
        """Content type of current playing media."""
        return MEDIA_TYPE_MUSIC

    @property
    def media_artist(self):
        """Artist of current playing media, music track only."""
        return self._media_artist

    @property
    def media_album_name(self):
        """Album name of current playing media, music track only."""
        return self._media_album

    @property
    def media_duration(self):
        """Duration of current playing media in seconds."""
        return self._media_duration

    def select_source(self, source):
        """Choose a different Pandora station and play it."""
        try:
            station_index = self._stations.index(source)
        except ValueError:
            _LOGGER.warning("Station %s is not in list", source)
            return
        _LOGGER.debug("Setting station %s, %d", source, station_index)
        self._send_station_list_command()
        self._pianobar.sendline('{}'.format(station_index))
        self._pianobar.expect('\r\n')
        self._player_state = STATE_PLAYING

    def _send_station_list_command(self):
        """Send a station list command."""
        import pexpect
        self._pianobar.send('s')
        try:
            self._pianobar.expect('Select station:', timeout=1)
        except pexpect.exceptions.TIMEOUT:
            # try again. Buffer was contaminated.
            self._clear_buffer()
            self._pianobar.send('s')
            self._pianobar.expect('Select station:')

    def update_playing_status(self):
        """Query pianobar for info about current media_title, station."""
        response = self._query_for_playing_status()
        if not response:
            return
        self._update_current_station(response)
        self._update_current_song(response)
        self._update_song_position()

    def _query_for_playing_status(self):
        """Query system for info about current track."""
        import pexpect
        self._clear_buffer()
        self._pianobar.send('i')
        try:
            match_idx = self._pianobar.expect([br'(\d\d):(\d\d)/(\d\d):(\d\d)',
                                               'No song playing',
                                               'Select station',
                                               'Receiving new playlist'])
        except pexpect.exceptions.EOF:
            _LOGGER.info("Pianobar process already exited")
            return None

        self._log_match()
        if match_idx == 1:
            # idle.
            response = None
        elif match_idx == 2:
            # stuck on a station selection dialog. Clear it.
            _LOGGER.warning("On unexpected station list page")
            self._pianobar.sendcontrol('m')  # press enter
            self._pianobar.sendcontrol('m')  # do it again b/c an 'i' got in
            response = self.update_playing_status()
        elif match_idx == 3:
            _LOGGER.debug("Received new playlist list")
            response = self.update_playing_status()
        else:
            response = self._pianobar.before.decode('utf-8')
        return response

    def _update_current_station(self, response):
        """Update current station."""
        station_match = re.search(STATION_PATTERN, response)
        if station_match:
            self._station = station_match.group(1)
            _LOGGER.debug("Got station as: %s", self._station)
        else:
            _LOGGER.warning("No station match")

    def _update_current_song(self, response):
        """Update info about current song."""
        song_match = re.search(CURRENT_SONG_PATTERN, response)
        if song_match:
            (self._media_title, self._media_artist,
             self._media_album) = song_match.groups()
            _LOGGER.debug("Got song as: %s", self._media_title)
        else:
            _LOGGER.warning("No song match")

    @util.Throttle(MIN_TIME_BETWEEN_UPDATES)
    def _update_song_position(self):
        """
        Get the song position and duration.

        It's hard to predict whether or not the music will start during init
        so we have to detect state by checking the ticker.

        """
        (cur_minutes, cur_seconds,
         total_minutes, total_seconds) = self._pianobar.match.groups()
        time_remaining = int(cur_minutes) * 60 + int(cur_seconds)
        self._media_duration = int(total_minutes) * 60 + int(total_seconds)

        if (time_remaining != self._time_remaining and
                time_remaining != self._media_duration):
            self._player_state = STATE_PLAYING
        elif self._player_state == STATE_PLAYING:
            self._player_state = STATE_PAUSED
        self._time_remaining = time_remaining

    def _log_match(self):
        """Log grabbed values from console."""
        _LOGGER.debug("Before: %s\nMatch: %s\nAfter: %s",
                      repr(self._pianobar.before),
                      repr(self._pianobar.match),
                      repr(self._pianobar.after))

    def _send_pianobar_command(self, service_cmd):
        """Send a command to Pianobar."""
        command = CMD_MAP.get(service_cmd)
        _LOGGER.debug(
            "Sending pinaobar command %s for %s", command, service_cmd)
        if command is None:
            _LOGGER.info("Command %s not supported yet", service_cmd)
        self._clear_buffer()
        self._pianobar.sendline(command)

    def _update_stations(self):
        """List defined Pandora stations."""
        self._send_station_list_command()
        station_lines = self._pianobar.before.decode('utf-8')
        _LOGGER.debug("Getting stations: %s", station_lines)
        self._stations = []
        for line in station_lines.split('\r\n'):
            match = re.search(r'\d+\).....(.+)', line)
            if match:
                station = match.group(1).strip()
                _LOGGER.debug("Found station %s", station)
                self._stations.append(station)
            else:
                _LOGGER.debug("No station match on %s", line)
        self._pianobar.sendcontrol('m')  # press enter with blank line
        self._pianobar.sendcontrol('m')  # do it twice in case an 'i' got in

    def _clear_buffer(self):
        """
        Clear buffer from pexpect.

        This is necessary because there are a bunch of 00:00 in the buffer

        """
        import pexpect
        try:
            while not self._pianobar.expect('.+', timeout=0.1):
                pass
        except pexpect.exceptions.TIMEOUT:
            pass
        except pexpect.exceptions.EOF:
            pass


def _pianobar_exists():
    """Verify that Pianobar is properly installed."""
    pianobar_exe = shutil.which('pianobar')
    if pianobar_exe:
        return True

    _LOGGER.warning(
        "The Pandora component depends on the Pianobar client, which "
        "cannot be found. Please install using instructions at "
        "https://home-assistant.io/components/media_player.pandora/")
    return False
