"""Support to interface with Plexamp integration."""

import logging

import voluptuous as vol

from homeassistant.components.media_player import (
    PLATFORM_SCHEMA,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    RepeatMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME, STATE_IDLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_PLEX_IP_ADDRESS, CONF_PLEX_TOKEN, DOMAIN, REPEAT_MODE_TO_NUMBER
from .services import PlexampService

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

    devices: list[dict] = entry.data["devices"]
    entities: list[PlexampMediaPlayer] = []

    _LOGGER.debug("Found devices %s", devices)

    for device in devices:
        plex_token = entry.data.get(CONF_PLEX_TOKEN, None)
        plex_ip_address = entry.data.get(CONF_PLEX_IP_ADDRESS, None)
        entity = PlexampMediaPlayer(
            device.get("name"),
            device.get("host"),
            plex_token,
            plex_ip_address,
            device.get("identifier"),
        )
        entities.append(entity)

    async_add_entities(entities, update_before_add=True)


class PlexampMediaPlayer(MediaPlayerEntity):
    """Representation of a Plexamp media player."""

    def __init__(
        self,
        name: str,
        host: str,
        plex_token: str | None,
        plex_ip_address: str | None,
        plex_identifier: str,
    ) -> None:
        """Initialize the Plexamp device."""
        self._attr_unique_id = f"Plexamp_{name}"
        self._plex_identifier = plex_identifier
        self._attr_name = f"Plexamp {name}"
        self._attr_state = STATE_IDLE
        self._host = host
        self._plex_token = plex_token
        self._plex_ip_address = plex_ip_address
        self._plexamp_service = PlexampService(
            plex_token=plex_token,
            plex_identifier=plex_identifier,
            plex_ip_address=plex_ip_address,
            host=host,
            device_name=name,
        )

        _LOGGER.debug("Creating new device: %s", name)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, name)},
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
        device_information = self._plexamp_service.get_device_information()
        _LOGGER.debug("device_information: %s", device_information)

        if device_information:
            self._attr_state = device_information["state"]
            self._attr_media_image_url = device_information.get("thumb")
            self._attr_media_title = device_information.get("title")
            self._attr_media_album_name = device_information.get("parent_title")
            self._attr_media_artist = device_information.get("grandparent_title")

    def media_play(self) -> None:
        """Send play command."""
        self._plexamp_service.send_playback_command(action="play")

    def media_pause(self) -> None:
        """Send pause command."""
        self._plexamp_service.send_playback_command(action="pause")

    def media_stop(self) -> None:
        """Send pause command."""
        self._plexamp_service.send_playback_command("stop")

    def media_next_track(self) -> None:
        """Send next command."""
        self._plexamp_service.send_playback_command("skipNext")

    def media_previous_track(self) -> None:
        """Send previous command."""
        self._plexamp_service.send_playback_command("skipPrevious")

    def set_shuffle(self, shuffle: bool) -> None:
        """Send shuffle command based on the specified mode."""
        should_shuffle = "1" if shuffle else "0"
        self._plexamp_service.send_set_parameter_command(f"shuffle={should_shuffle}")

    def set_repeat(self, repeat: RepeatMode) -> None:
        """Send repeat command based on the specified mode."""

        repeat_value = REPEAT_MODE_TO_NUMBER.get(
            repeat, "0"
        )  # Default to "0" (OFF) if repeat mode is unknown
        self._plexamp_service.send_set_parameter_command(f"repeat={repeat_value}")

    def mute_volume(self, mute: bool) -> None:
        """Mute the volume."""
        self._plexamp_service.send_set_parameter_command("volume=0")

    def set_volume_level(self, volume: float) -> None:
        """Set volume level, range 0..1."""
        converted_volume = volume * 100
        self._plexamp_service.send_set_parameter_command(f"volume={converted_volume}")
