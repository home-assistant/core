"""Support to interface with Plexamp integration."""

import logging
import xml.etree.ElementTree as ET

import requests
import voluptuous as vol

from homeassistant.components.media_player import (
    PLATFORM_SCHEMA,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    RepeatMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME, STATE_OFF
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_PLEX_IP_ADDRESS,
    CONF_PLEX_TOKEN,
    DOMAIN,
    NUMBER_TO_REPEAT_MODE,
    POLL_COMMAND_ID,
    POLL_INCLUDE_METADA,
    POLL_WAIT,
    REPEAT_MODE_TO_NUMBER,
)
from .utils import replace_ip_prefix

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): vol.All(str),
        vol.Optional(CONF_NAME, default="Plexamp"): vol.All(str),
    }
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Plexamp media player from a config entry."""
    host = entry.data[CONF_HOST]
    name = entry.title
    plex_token = entry.data.get(CONF_PLEX_TOKEN)
    plex_ip_address = entry.data.get(CONF_PLEX_IP_ADDRESS)

    _LOGGER.debug("async_setup_entry up new media_player: %s", host)
    async_add_entities(
        [PlexampMediaPlayer(name, host, plex_token, plex_ip_address)],
        update_before_add=True,
    )


class PlexampMediaPlayer(MediaPlayerEntity):
    """Representation of a Plexamp media player."""

    def __init__(
        self, name: str, host: str, plex_token: str | None, plex_ip_address: str | None
    ) -> None:
        """Initialize the Plexamp device."""
        self._attr_unique_id = f"plexamp_{host.replace('.', '_')}"
        self._name = name
        self._attr_state = STATE_OFF
        self._host = f"http://{host}:32500"
        self._plex_token = plex_token
        self._plex_ip_address = plex_ip_address

        _LOGGER.debug("__init__ starting new device: %s", host)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, host)},
            name=name,
            manufacturer="Plexamp",
        )

    @property
    def supported_features(self) -> MediaPlayerEntityFeature:
        """Flag media player features that are supported."""
        return (
            MediaPlayerEntityFeature.PLAY
            | MediaPlayerEntityFeature.PAUSE
            | MediaPlayerEntityFeature.STOP
            | MediaPlayerEntityFeature.NEXT_TRACK
            | MediaPlayerEntityFeature.PREVIOUS_TRACK
            | MediaPlayerEntityFeature.SHUFFLE_SET
            | MediaPlayerEntityFeature.REPEAT_SET
            | MediaPlayerEntityFeature.VOLUME_SET
            | MediaPlayerEntityFeature.VOLUME_MUTE
            | MediaPlayerEntityFeature.VOLUME_STEP
        )

    def update(self) -> None:
        """Retrieve the latest data from the device."""
        base_url = f"{self._host}/player/timeline/poll"
        url = f"{base_url}?wait={POLL_WAIT}&includeMetadata={POLL_INCLUDE_METADA}&commandID={POLL_COMMAND_ID}"
        _LOGGER.debug("Updating device: %s", self._name)

        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            content = response.content
            root = ET.fromstring(content)

            for timeline in root.findall("Timeline"):
                if timeline.get("itemType") == "music":
                    status = timeline.get("state", MediaPlayerState.IDLE)
                    self._attr_state = {
                        "playing": MediaPlayerState.PLAYING,
                        "paused": MediaPlayerState.PAUSED,
                    }.get(status)

                    self._attr_shuffle = timeline.get("shuffle", 0) != "0"
                    self._attr_volume_level = float(timeline.get("volume", 1.0)) / 100
                    self._attr_volume_step = 0.1

                    repeat_mode_value = timeline.get("repeat", 0)
                    self._attr_repeat = NUMBER_TO_REPEAT_MODE.get(repeat_mode_value)

                    track = timeline.find("Track")
                    if track is not None:
                        # Extract the title from the Track element
                        self._attr_media_title = track.get("title", None)
                        self._attr_media_album_name = track.get("parentTitle", None)
                        self._attr_media_artist = track.get("grandparentTitle", None)

                        if self._plex_token and self._plex_ip_address:
                            formatted_ip_address = self._plex_ip_address.replace(
                                ".", "-"
                            )
                            protocol = timeline.get("protocol", None)
                            address = replace_ip_prefix(
                                timeline.get("address", None), formatted_ip_address
                            )
                            port = timeline.get("port", "32500")
                            album_base_url = f"{protocol}://{address}:{port}"
                            thumb = track.get("thumb", None)
                            self._attr_media_image_url = f"{album_base_url}/photo/:/transcode?width=300&height=300&url={thumb}&quality=90&format=jpeg&X-Plex-Token={self._plex_token}"
                    else:
                        self._attr_media_title = None
                        self._attr_media_album_name = None
                        self._attr_media_artist = None

                    # plexamp does not support photo and video, returned by Plex
                    break
        except Exception as e:
            _LOGGER.error("Error updating Plexamp status: %s", e)
            self._attr_state = STATE_OFF

    def media_play(self) -> None:
        """Send play command."""
        self._send_playback_command("play")

    def media_pause(self) -> None:
        """Send pause command."""
        self._send_playback_command("pause")

    def media_stop(self) -> None:
        """Send pause command."""
        self._send_playback_command("stop")

    def media_next_track(self) -> None:
        """Send next command."""
        self._send_playback_command("skipNext")

    def media_previous_track(self) -> None:
        """Send previous command."""
        self._send_playback_command("skipPrevious")

    def set_shuffle(self, shuffle: bool) -> None:
        """Send shuffle command based on the specified mode."""
        should_shuffle = "1" if shuffle else "0"
        self._send_set_parameter_command(f"shuffle={should_shuffle}")

    def set_repeat(self, repeat: RepeatMode) -> None:
        """Send repeat command based on the specified mode."""

        repeat_value = REPEAT_MODE_TO_NUMBER.get(
            repeat, "0"
        )  # Default to "0" (OFF) if repeat mode is unknown
        self._send_set_parameter_command(f"repeat={repeat_value}")

    def mute_volume(self, mute: bool) -> None:
        """Mute the volume."""
        self._send_set_parameter_command("volume=0")

    def set_volume_level(self, volume: float) -> None:
        """Set volume level, range 0..1."""
        converted_volume = volume * 100
        self._send_set_parameter_command(f"volume={converted_volume}")

    def _send_playback_command(self, action: str):
        """Send a command to the player."""
        url = f"{self._host}/player/playback/{action}"
        _LOGGER.debug("Sending playback command to %s: %s", self._name, url)
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
        except Exception as e:
            _LOGGER.error("Failed to send command %s in %s: %s", action, self._name, e)

    def _send_set_parameter_command(self, parameters: str):
        """Send a parameter command to the player."""

        url = f"{self._host}/player/playback/setParameters?{parameters}"
        _LOGGER.debug("Sending parameter command to %s: %s", self._name, url)
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
        except Exception as e:
            _LOGGER.error(
                "Failed to set parameter %s in %s: %s",
                parameters,
                self._name,
                e,
            )
