"""Support for Logitech UE Smart Radios."""
from __future__ import annotations

import logging

import requests
import voluptuous as vol

from homeassistant.components.media_player import (
    PLATFORM_SCHEMA,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
)
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

_LOGGER = logging.getLogger(__name__)

ICON = "mdi:radio"
URL = "http://decibel.logitechmusic.com/jsonrpc.js"

PLAYBACK_DICT = {
    "play": MediaPlayerState.PLAYING,
    "pause": MediaPlayerState.PAUSED,
    "stop": MediaPlayerState.IDLE,
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_USERNAME): cv.string, vol.Required(CONF_PASSWORD): cv.string}
)


def send_request(payload, session):
    """Send request to radio."""
    try:
        request = requests.post(
            URL,
            cookies={"sdi_squeezenetwork_session": session},
            json=payload,
            timeout=5,
        )
    except requests.exceptions.Timeout:
        _LOGGER.error("Timed out when sending request")
    except requests.exceptions.ConnectionError:
        _LOGGER.error("An error occurred while connecting")
    else:
        return request.json()


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Logitech UE Smart Radio platform."""
    email = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)

    session_request = requests.post(
        "https://www.uesmartradio.com/user/login",
        data={"email": email, "password": password},
        timeout=5,
    )
    session = session_request.cookies["sdi_squeezenetwork_session"]

    player_request = send_request({"params": ["", ["serverstatus"]]}, session)

    players = [
        UERadioDevice(session, player["playerid"], player["name"])
        for player in player_request["result"]["players_loop"]
    ]

    add_entities(players)


class UERadioDevice(MediaPlayerEntity):
    """Representation of a Logitech UE Smart Radio device."""

    _attr_media_content_type = MediaType.MUSIC
    _attr_supported_features = (
        MediaPlayerEntityFeature.PLAY
        | MediaPlayerEntityFeature.PAUSE
        | MediaPlayerEntityFeature.STOP
        | MediaPlayerEntityFeature.PREVIOUS_TRACK
        | MediaPlayerEntityFeature.NEXT_TRACK
        | MediaPlayerEntityFeature.TURN_ON
        | MediaPlayerEntityFeature.TURN_OFF
        | MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.VOLUME_MUTE
    )

    def __init__(self, session, player_id, player_name):
        """Initialize the Logitech UE Smart Radio device."""
        self._session = session
        self._player_id = player_id
        self._name = player_name
        self._state = None
        self._volume = 0
        self._last_volume = 0
        self._media_title = None
        self._media_artist = None
        self._media_artwork_url = None

    def send_command(self, command):
        """Send command to radio."""
        send_request(
            {"method": "slim.request", "params": [self._player_id, command]},
            self._session,
        )

    def update(self) -> None:
        """Get the latest details from the device."""
        request = send_request(
            {
                "method": "slim.request",
                "params": [
                    self._player_id,
                    ["status", "-", 1, "tags:cgABbehldiqtyrSuoKLN"],
                ],
            },
            self._session,
        )

        if request["error"] is not None:
            self._state = None
            return

        if request["result"]["power"] == 0:
            self._state = MediaPlayerState.OFF
        else:
            self._state = PLAYBACK_DICT[request["result"]["mode"]]

        media_info = request["result"]["playlist_loop"][0]

        self._volume = request["result"]["mixer volume"] / 100
        self._media_artwork_url = media_info["artwork_url"]
        self._media_title = media_info["title"]
        if "artist" in media_info:
            self._media_artist = media_info["artist"]
        else:
            self._media_artist = media_info.get("remote_title")

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
    def is_volume_muted(self):
        """Boolean if volume is currently muted."""
        return self._volume <= 0

    @property
    def volume_level(self):
        """Volume level of the media player (0..1)."""
        return self._volume

    @property
    def media_image_url(self):
        """Image URL of current playing media."""
        return self._media_artwork_url

    @property
    def media_artist(self):
        """Artist of current playing media, music track only."""
        return self._media_artist

    @property
    def media_title(self):
        """Title of current playing media."""
        return self._media_title

    def turn_on(self) -> None:
        """Turn on specified media player or all."""
        self.send_command(["power", 1])

    def turn_off(self) -> None:
        """Turn off specified media player or all."""
        self.send_command(["power", 0])

    def media_play(self) -> None:
        """Send the media player the command for play/pause."""
        self.send_command(["play"])

    def media_pause(self) -> None:
        """Send the media player the command for pause."""
        self.send_command(["pause"])

    def media_stop(self) -> None:
        """Send the media player the stop command."""
        self.send_command(["stop"])

    def media_previous_track(self) -> None:
        """Send the media player the command for prev track."""
        self.send_command(["button", "rew"])

    def media_next_track(self) -> None:
        """Send the media player the command for next track."""
        self.send_command(["button", "fwd"])

    def mute_volume(self, mute: bool) -> None:
        """Send mute command."""
        if mute:
            self._last_volume = self._volume
            self.send_command(["mixer", "volume", 0])
        else:
            self.send_command(["mixer", "volume", self._last_volume * 100])

    def set_volume_level(self, volume: float) -> None:
        """Set volume level, range 0..1."""
        self.send_command(["mixer", "volume", volume * 100])
