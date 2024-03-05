"""Support to interface with Plexamp integration."""

import logging

import voluptuous as vol

from homeassistant.components.media_player import (
    PLATFORM_SCHEMA,
    BrowseMedia,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    RepeatMode,
)
from homeassistant.components.media_player.const import (
    MEDIA_CLASS_ALBUM,
    MEDIA_CLASS_ARTIST,
    MEDIA_CLASS_PLAYLIST,
    MediaType,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME, STATE_IDLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt
from .const import CONF_PLEX_TOKEN, DOMAIN, REPEAT_MODE_TO_NUMBER
from .models import BaseMediaPlayerFactory
from .plexamp_service import PlexampService

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
        entity = PlexampMediaPlayer(
            BaseMediaPlayerFactory.from_dict(device),
            plex_token=plex_token,
        )
        entities.append(entity)

    async_add_entities(entities, update_before_add=True)


class PlexampMediaPlayer(MediaPlayerEntity):
    """Representation of a Plexamp media player."""

    def __init__(
        self,
        entity: BaseMediaPlayerFactory,
        plex_token: str | None,
    ) -> None:
        """Initialize the Plexamp device."""
        self._attr_unique_id = f"Plexamp_{entity.name}"
        self._attr_name = f"Plexamp {entity.name}"
        self._plexamp_entity = entity
        self._attr_state = STATE_IDLE
        self._volume_before_mute = self._attr_volume_level or 0.15

        self._plexamp_service = PlexampService(
            plexamp_entity=entity,
            plex_token=plex_token,
        )

        _LOGGER.debug("Creating new device: %s", self._attr_name)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._attr_name)},
            name=self._attr_name,
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
            | MediaPlayerEntityFeature.SHUFFLE_SET
            | MediaPlayerEntityFeature.REPEAT_SET
            | MediaPlayerEntityFeature.VOLUME_SET
            | MediaPlayerEntityFeature.VOLUME_MUTE
            | MediaPlayerEntityFeature.VOLUME_STEP
            | MediaPlayerEntityFeature.PLAY_MEDIA
            | MediaPlayerEntityFeature.BROWSE_MEDIA
        )

    async def async_update(self) -> None:
        """Retrieve the latest data from the device."""
        device_information = await self._plexamp_service.poll_device()
        if device_information:
            self._attr_state = device_information["state"]
            self._attr_media_image_url = device_information.get("thumb")
            self._attr_media_title = device_information.get("title")
            self._attr_media_album_name = device_information.get("parent_title")
            self._attr_media_artist = device_information.get("grandparent_title")
            self._attr_media_duration = device_information.get("duration")
            self._attr_media_position = device_information.get("time")
            self._attr_media_position_updated_at = dt.utcnow()
            self._attr_shuffle = device_information.get("shuffle")
            self._attr_repeat = device_information.get("repeat")
            self._attr_volume_level = device_information.get("volume")
            self._attr_is_volume_muted = device_information.get("volume") <= 0.0

    async def async_media_play(self) -> None:
        """Send play command."""
        await self._plexamp_service.send_playback_command(action="play")

    async def async_media_pause(self) -> None:
        """Send pause command."""
        await self._plexamp_service.send_playback_command(action="pause")

    async def async_media_stop(self) -> None:
        """Send pause command."""
        await self._plexamp_service.send_playback_command("stop")

    async def async_media_next_track(self) -> None:
        """Send next command."""
        await self._plexamp_service.send_playback_command("skipNext")

    async def async_media_previous_track(self) -> None:
        """Send previous command."""
        await self._plexamp_service.send_playback_command("skipPrevious")

    async def async_set_shuffle(self, shuffle: bool) -> None:
        """Send shuffle command based on the specified mode."""
        should_shuffle = "1" if shuffle else "0"
        await self._plexamp_service.send_set_parameter_command(
            f"shuffle={should_shuffle}"
        )

    async def async_set_repeat(self, repeat: RepeatMode) -> None:
        """Send repeat command based on the specified mode."""
        repeat_value = REPEAT_MODE_TO_NUMBER.get(
            repeat, "0"
        )  # Default to "0" (OFF) if repeat mode is unknown
        await self._plexamp_service.send_set_parameter_command(f"repeat={repeat_value}")

    async def async_mute_volume(self, mute: bool) -> None:
        """Mute the volume."""
        _LOGGER.error("Mute volume: %s", mute)
        if mute:
            self._volume_before_mute = self._attr_volume_level
            await self.async_set_volume_level(0.0)
        if not mute:
            _LOGGER.error("_volume_before_mute: %s", self._volume_before_mute)
            await self.async_set_volume_level(self._volume_before_mute)

    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level, range 0..1."""
        converted_volume = volume * 100
        await self._plexamp_service.send_set_parameter_command(
            f"volume={converted_volume}"
        )

    async def async_play_media(
        self, media_type: MediaType | str, media_id: str, **kwargs
    ):
        """Implement media playback."""
        # Handle playlist selection
        if media_type == "playlist":
            await self._plexamp_service.play_media(
                media_type=media_type,
                rating_key=media_id,
                shuffle=1 if self._attr_shuffle else 0,
            )
        # Handle track selection
        elif media_type == "track":
            # Send command to start playing the selected track
            pass

    async def async_browse_media(
        self, media_content_type, media_content_id
    ) -> BrowseMedia:
        """Implement the browsing media method."""

        # Root level browsing
        if media_content_id is None:
            # Define your root level content here
            return BrowseMedia(
                title="Plexamp Media",
                media_class=MEDIA_CLASS_ARTIST,
                media_content_id="root",
                media_content_type="artist",
                can_expand=True,
                can_play=False,
                children=[
                    BrowseMedia(
                        title="Albums",
                        media_class=MEDIA_CLASS_ALBUM,
                        media_content_id="albums",
                        media_content_type="albums",
                        can_expand=True,
                        can_play=False,
                    )
                ],
            )

        # Handle browsing for specific categories (e.g., albums)
        if media_content_id == "albums":
            # Fetch album data from your integration
            playlists = await self._plexamp_service.get_playlists()

            # Construct browse media response
            album_items = []
            for playlist in playlists:
                album_items.append(
                    BrowseMedia(
                        title=playlist["title"],
                        media_class=MEDIA_CLASS_PLAYLIST,
                        media_content_id=playlist["ratingKey"],
                        media_content_type=MEDIA_CLASS_PLAYLIST,
                        can_expand=False,
                        can_play=True,
                    )
                )

            return BrowseMedia(
                title="Albums",
                media_class=MEDIA_CLASS_ALBUM,
                media_content_id="album",
                media_content_type="library",
                can_expand=True,
                can_play=False,
                children=album_items,
            )

        # Handle other specific media_content_ids as needed
        # You can add more conditionals for different categories

        return BrowseMedia(media_content_type="library")
