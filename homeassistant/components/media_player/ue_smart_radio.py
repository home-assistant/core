"""
Support for Logitech UE Smart Radios.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/media_player.ue_smart_radio/
"""

import logging
from json import dumps
import voluptuous as vol
import requests

from homeassistant.components.media_player import (
    MediaPlayerDevice, MEDIA_TYPE_MUSIC, PLATFORM_SCHEMA,
    SUPPORT_PLAY, SUPPORT_PAUSE, SUPPORT_STOP, SUPPORT_PREVIOUS_TRACK,
    SUPPORT_NEXT_TRACK, SUPPORT_TURN_ON, SUPPORT_TURN_OFF, SUPPORT_VOLUME_SET,
    SUPPORT_VOLUME_MUTE)
from homeassistant.const import (
    CONF_EMAIL, CONF_PASSWORD, STATE_OFF, STATE_IDLE, STATE_PLAYING,
    STATE_PAUSED, STATE_UNKNOWN)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

ICON = "mdi:radio"

SUPPORT_UE_SMART_RADIO = SUPPORT_PLAY | SUPPORT_PAUSE | SUPPORT_STOP | \
    SUPPORT_PREVIOUS_TRACK | SUPPORT_NEXT_TRACK | SUPPORT_TURN_ON | \
    SUPPORT_TURN_OFF | SUPPORT_VOLUME_SET | SUPPORT_VOLUME_MUTE

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_EMAIL): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Logitech UE Smart Radio platform."""
    email = config.get(CONF_EMAIL)
    password = config.get(CONF_PASSWORD)

    session_request = requests.post("https://www.uesmartradio.com/user/login",
                                    data={"email": email, "password":
                                          password})
    session = session_request.cookies["sdi_squeezenetwork_session"]

    player_request = requests.post("http://decibel.logitechmusic.com/jsonrpc \
                                   .js", cookies={"sdi_squeezenetwork_session":
                                                  session},
                                   data="{\"params\":[\"\", \
                                        [\"serverstatus\"]]}").json()
    player_id = player_request["result"]["players_loop"][0]["playerid"]
    player_name = player_request["result"]["players_loop"][0]["name"]

    add_devices([UERadioDevice(session, player_id, player_name)])


class UERadioDevice(MediaPlayerDevice):
    """Representation of a Logitech UE Smart Radio device."""

    def __init__(self, session, player_id, player_name):
        """Initialize the Logitech UE Smart Radio device."""
        self._session = session
        self._player_id = player_id
        self._name = player_name
        self._state = STATE_UNKNOWN
        self._volume = 0
        self._last_volume = 0
        self._media_title = None
        self._media_artist = None
        self._media_artwork_url = None

    def send_command(self, command):
        """Send request to radio."""
        payload = ("{{\"method\":\"slim.request\",\"params\":[\"{}\",{}]}}"
                   .format(self._player_id, dumps(command)))
        try:
            requests.post("http://decibel.logitechmusic.com/jsonrpc.js",
                          cookies={"sdi_squeezenetwork_session":
                                   self._session},
                          data=payload, timeout=5)
        except requests.exceptions.Timeout:
            _LOGGER.error("Timed out when sending command to UE Smart Radio")

    def update(self):
        """Get the latest details from the device."""
        payload = ("{{\"method\":\"slim.request\",\"params\":[\"{}\", \
                   [\"status\",\"-\",1,\"tags:cgABbehldiqtyrSuoKLN\"]]}}"
                   .format(self._player_id))
        try:
            request = (requests.post("http://decibel.logitechmusic.com/ \
                                     jsonrpc.js",
                                     cookies={"sdi_squeezenetwork_session":
                                              self._session}, data=payload,
                                     timeout=5).json())
        except requests.exceptions.Timeout:
            _LOGGER.error("Timed out when retrieving status of UE Smart Radio")
            return

        if request["error"] is not None:
            self._state = STATE_UNKNOWN
            return

        if request["result"]["power"] == 0:
            self._state = STATE_OFF
        else:
            self._state = {
                "play": STATE_PLAYING,
                "pause": STATE_PAUSED,
                "stop": STATE_IDLE
            }.get(request["result"]["mode"])

        media_info = request["result"]["playlist_loop"][0]

        self._volume = request["result"]["mixer volume"] / 100
        self._media_artwork_url = media_info["artwork_url"]
        self._media_title = media_info["title"]
        if "artist" in media_info:
            self._media_artist = media_info["artist"]
        else:
            self._media_artist = (media_info["remote_title"] if "remote_title"
                                  in media_info else None)

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        return ICON

    @property
    def should_poll(self):
        """Push an update after each command."""
        return True

    @property
    def is_volume_muted(self):
        """Boolean if volume is currently muted."""
        return True if self._volume <= 0 else False

    @property
    def volume_level(self):
        """Volume level of the media player (0..1)."""
        return self._volume

    @property
    def supported_features(self):
        """Flag of features that are supported."""
        return SUPPORT_UE_SMART_RADIO

    @property
    def media_content_type(self):
        """Return the media content type."""
        return MEDIA_TYPE_MUSIC

    @property
    def media_image_url(self):
        """Image url of current playing media."""
        return self._media_artwork_url

    @property
    def media_artist(self):
        """Artist of current playing media, music track only."""
        return self._media_artist

    @property
    def media_title(self):
        """Title of current playing media."""
        return self._media_title

    def turn_on(self):
        """Turn on specified media player or all."""
        self.send_command(["power", 1])

    def turn_off(self):
        """Turn off specified media player or all."""
        self.send_command(["power", 0])

    def media_play(self):
        """Send the media player the command for play/pause."""
        self.send_command(["play"])

    def media_pause(self):
        """Send the media player the command for pause."""
        self.send_command(["pause"])

    def media_stop(self):
        """Send the media player the stop command."""
        self.send_command(["stop"])

    def media_previous_track(self):
        """Send the media player the command for prev track."""
        self.send_command(["button", "rew"])

    def media_next_track(self):
        """Send the media player the command for next track."""
        self.send_command(["button", "fwd"])

    def mute_volume(self, mute):
        """Send mute command."""
        if mute:
            self._last_volume = self._volume
            self.send_command(["mixer", "volume", 0])
        else:
            self.send_command(["mixer", "volume", self._last_volume * 100])

    def set_volume_level(self, volume):
        """Set volume level, range 0..1."""
        self.send_command(["mixer", "volume", volume * 100])
