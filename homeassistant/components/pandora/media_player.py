"""Component for controlling Pandora stations through the pianobar client."""

from __future__ import annotations

from datetime import timedelta
import logging
import os
import re
import shutil
import signal

import pexpect

from homeassistant import util
from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
)
from homeassistant.const import (
    EVENT_HOMEASSISTANT_STOP,
    SERVICE_MEDIA_NEXT_TRACK,
    SERVICE_MEDIA_PLAY,
    SERVICE_MEDIA_PLAY_PAUSE,
    SERVICE_VOLUME_DOWN,
    SERVICE_VOLUME_UP,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

_LOGGER = logging.getLogger(__name__)


CMD_MAP = {
    SERVICE_MEDIA_NEXT_TRACK: "n",
    SERVICE_MEDIA_PLAY_PAUSE: "p",
    SERVICE_MEDIA_PLAY: "p",
    SERVICE_VOLUME_UP: ")",
    SERVICE_VOLUME_DOWN: "(",
}
MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=2)
CURRENT_SONG_PATTERN = re.compile(r'"(.*?)"\s+by\s+"(.*?)"\son\s+"(.*?)"', re.MULTILINE)
STATION_PATTERN = re.compile(r'Station\s"(.+?)"', re.MULTILINE)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Pandora media player platform."""
    if not _pianobar_exists():
        return
    pandora = PandoraMediaPlayer("Pandora")

    # Make sure we end the pandora subprocess on exit in case user doesn't
    # power it down.
    def _stop_pianobar(_event):
        pandora.turn_off()

    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, _stop_pianobar)
    add_entities([pandora])


class PandoraMediaPlayer(MediaPlayerEntity):
    """A media player that uses the Pianobar interface to Pandora."""

    _attr_media_content_type = MediaType.MUSIC
    # MediaPlayerEntityFeature.VOLUME_SET is close to available
    # but we need volume up/down controls in the GUI.
    _attr_supported_features = (
        MediaPlayerEntityFeature.PAUSE
        | MediaPlayerEntityFeature.TURN_ON
        | MediaPlayerEntityFeature.TURN_OFF
        | MediaPlayerEntityFeature.NEXT_TRACK
        | MediaPlayerEntityFeature.SELECT_SOURCE
        | MediaPlayerEntityFeature.PLAY
    )

    def __init__(self, name):
        """Initialize the Pandora device."""
        self._attr_name = name
        self._attr_state = MediaPlayerState.OFF
        self._attr_source = ""
        self._attr_media_title = ""
        self._attr_media_artist = ""
        self._attr_media_album_name = ""
        self._attr_source_list = []
        self._time_remaining = 0
        self._attr_media_duration = 0
        self._pianobar = None

    def turn_on(self) -> None:
        """Turn the media player on."""
        if self.state != MediaPlayerState.OFF:
            return
        self._pianobar = pexpect.spawn("pianobar")
        _LOGGER.debug("Started pianobar subprocess")
        mode = self._pianobar.expect(
            ["Receiving new playlist", "Select station:", "Email:"]
        )
        if mode == 1:
            # station list was presented. dismiss it.
            self._pianobar.sendcontrol("m")
        elif mode == 2:
            _LOGGER.warning(
                "The pianobar client is not configured to log in. "
                "Please create a configuration file for it as described at "
                "https://www.home-assistant.io/integrations/pandora/"
            )
            # pass through the email/password prompts to quit cleanly
            self._pianobar.sendcontrol("m")
            self._pianobar.sendcontrol("m")
            self._pianobar.terminate()
            self._pianobar = None
            return
        self._update_stations()
        self.update_playing_status()

        self._attr_state = MediaPlayerState.IDLE
        self.schedule_update_ha_state()

    def turn_off(self) -> None:
        """Turn the media player off."""
        if self._pianobar is None:
            _LOGGER.warning("Pianobar subprocess already stopped")
            return
        self._pianobar.send("q")
        try:
            _LOGGER.debug("Stopped Pianobar subprocess")
            self._pianobar.terminate()
        except pexpect.exceptions.TIMEOUT:
            # kill the process group
            os.killpg(os.getpgid(self._pianobar.pid), signal.SIGTERM)
            _LOGGER.debug("Killed Pianobar subprocess")
        self._pianobar = None
        self._attr_state = MediaPlayerState.OFF
        self.schedule_update_ha_state()

    def media_play(self) -> None:
        """Send play command."""
        self._send_pianobar_command(SERVICE_MEDIA_PLAY_PAUSE)
        self._attr_state = MediaPlayerState.PLAYING
        self.schedule_update_ha_state()

    def media_pause(self) -> None:
        """Send pause command."""
        self._send_pianobar_command(SERVICE_MEDIA_PLAY_PAUSE)
        self._attr_state = MediaPlayerState.PAUSED
        self.schedule_update_ha_state()

    def media_next_track(self) -> None:
        """Go to next track."""
        self._send_pianobar_command(SERVICE_MEDIA_NEXT_TRACK)
        self.schedule_update_ha_state()

    @property
    def media_title(self) -> str | None:
        """Title of current playing media."""
        self.update_playing_status()
        return self._attr_media_title

    def select_source(self, source: str) -> None:
        """Choose a different Pandora station and play it."""
        if self.source_list is None:
            return
        try:
            station_index = self.source_list.index(source)
        except ValueError:
            _LOGGER.warning("Station %s is not in list", source)
            return
        _LOGGER.debug("Setting station %s, %d", source, station_index)
        self._send_station_list_command()
        self._pianobar.sendline(f"{station_index}")
        self._pianobar.expect("\r\n")
        self._attr_state = MediaPlayerState.PLAYING

    def _send_station_list_command(self):
        """Send a station list command."""
        self._pianobar.send("s")
        try:
            self._pianobar.expect("Select station:", timeout=1)
        except pexpect.exceptions.TIMEOUT:
            # try again. Buffer was contaminated.
            self._clear_buffer()
            self._pianobar.send("s")
            self._pianobar.expect("Select station:")

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
        self._clear_buffer()
        self._pianobar.send("i")
        try:
            match_idx = self._pianobar.expect(
                [
                    rb"(\d\d):(\d\d)/(\d\d):(\d\d)",
                    "No song playing",
                    "Select station",
                    "Receiving new playlist",
                ]
            )
        except pexpect.exceptions.EOF:
            _LOGGER.warning("Pianobar process already exited")
            return None

        self._log_match()
        if match_idx == 1:
            # idle.
            response = None
        elif match_idx == 2:
            # stuck on a station selection dialog. Clear it.
            _LOGGER.warning("On unexpected station list page")
            self._pianobar.sendcontrol("m")  # press enter
            self._pianobar.sendcontrol("m")  # do it again b/c an 'i' got in
            response = self.update_playing_status()
        elif match_idx == 3:
            _LOGGER.debug("Received new playlist list")
            response = self.update_playing_status()
        else:
            response = self._pianobar.before.decode("utf-8")
        return response

    def _update_current_station(self, response):
        """Update current station."""
        if station_match := re.search(STATION_PATTERN, response):
            self._attr_source = station_match.group(1)
            _LOGGER.debug("Got station as: %s", self._attr_source)
        else:
            _LOGGER.warning("No station match")

    def _update_current_song(self, response):
        """Update info about current song."""
        if song_match := re.search(CURRENT_SONG_PATTERN, response):
            (
                self._attr_media_title,
                self._attr_media_artist,
                self._attr_media_album_name,
            ) = song_match.groups()
            _LOGGER.debug("Got song as: %s", self._attr_media_title)
        else:
            _LOGGER.warning("No song match")

    @util.Throttle(MIN_TIME_BETWEEN_UPDATES)
    def _update_song_position(self):
        """Get the song position and duration.

        It's hard to predict whether or not the music will start during init
        so we have to detect state by checking the ticker.

        """
        (
            cur_minutes,
            cur_seconds,
            total_minutes,
            total_seconds,
        ) = self._pianobar.match.groups()
        time_remaining = int(cur_minutes) * 60 + int(cur_seconds)
        self._attr_media_duration = int(total_minutes) * 60 + int(total_seconds)

        if time_remaining not in (self._time_remaining, self._attr_media_duration):
            self._attr_state = MediaPlayerState.PLAYING
        elif self.state == MediaPlayerState.PLAYING:
            self._attr_state = MediaPlayerState.PAUSED
        self._time_remaining = time_remaining

    def _log_match(self):
        """Log grabbed values from console."""
        _LOGGER.debug(
            "Before: %s\nMatch: %s\nAfter: %s",
            repr(self._pianobar.before),
            repr(self._pianobar.match),
            repr(self._pianobar.after),
        )

    def _send_pianobar_command(self, service_cmd):
        """Send a command to Pianobar."""
        command = CMD_MAP.get(service_cmd)
        _LOGGER.debug("Sending pinaobar command %s for %s", command, service_cmd)
        if command is None:
            _LOGGER.warning("Command %s not supported yet", service_cmd)
        self._clear_buffer()
        self._pianobar.sendline(command)

    def _update_stations(self):
        """List defined Pandora stations."""
        self._send_station_list_command()
        station_lines = self._pianobar.before.decode("utf-8")
        _LOGGER.debug("Getting stations: %s", station_lines)
        self._attr_source_list = []
        for line in station_lines.split("\r\n"):
            if match := re.search(r"\d+\).....(.+)", line):
                station = match.group(1).strip()
                _LOGGER.debug("Found station %s", station)
                self._attr_source_list.append(station)
            else:
                _LOGGER.debug("No station match on %s", line)
        self._pianobar.sendcontrol("m")  # press enter with blank line
        self._pianobar.sendcontrol("m")  # do it twice in case an 'i' got in

    def _clear_buffer(self):
        """Clear buffer from pexpect.

        This is necessary because there are a bunch of 00:00 in the buffer

        """
        try:
            while not self._pianobar.expect(".+", timeout=0.1):
                pass
        except pexpect.exceptions.TIMEOUT:
            pass
        except pexpect.exceptions.EOF:
            pass


def _pianobar_exists():
    """Verify that Pianobar is properly installed."""
    pianobar_exe = shutil.which("pianobar")
    if pianobar_exe:
        return True

    _LOGGER.warning(
        "The Pandora integration depends on the Pianobar client, which "
        "cannot be found. Please install using instructions at "
        "https://www.home-assistant.io/integrations/media_player.pandora/"
    )
    return False
