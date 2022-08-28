"""Play media via gstreamer."""
from __future__ import annotations

import logging
from typing import Any

from gsp import GstreamerPlayer
import voluptuous as vol

from homeassistant.components import media_source
from homeassistant.components.media_player import (
    PLATFORM_SCHEMA,
    BrowseMedia,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
)
from homeassistant.components.media_player.browse_media import (
    async_process_play_media_url,
)
from homeassistant.components.media_player.const import MEDIA_TYPE_MUSIC
from homeassistant.const import CONF_NAME, EVENT_HOMEASSISTANT_STOP, STATE_IDLE
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

_LOGGER = logging.getLogger(__name__)

CONF_PIPELINE = "pipeline"

DOMAIN = "gstreamer"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Optional(CONF_NAME): cv.string, vol.Optional(CONF_PIPELINE): cv.string}
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Gstreamer platform."""

    name = config.get(CONF_NAME)
    pipeline = config.get(CONF_PIPELINE)
    player = GstreamerPlayer(pipeline)

    def _shutdown(call):
        """Quit the player on shutdown."""
        player.quit()

    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, _shutdown)
    add_entities([GstreamerDevice(player, name)])


class GstreamerDevice(MediaPlayerEntity):
    """Representation of a Gstreamer device."""

    _attr_supported_features = (
        MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.PLAY
        | MediaPlayerEntityFeature.PAUSE
        | MediaPlayerEntityFeature.PLAY_MEDIA
        | MediaPlayerEntityFeature.NEXT_TRACK
        | MediaPlayerEntityFeature.BROWSE_MEDIA
    )

    def __init__(self, player, name):
        """Initialize the Gstreamer device."""
        self._player = player
        self._name = name or DOMAIN
        self._state = STATE_IDLE
        self._volume = None
        self._duration = None
        self._uri = None
        self._title = None
        self._artist = None
        self._album = None

    def update(self) -> None:
        """Update properties."""
        self._state = self._player.state
        self._volume = self._player.volume
        self._duration = self._player.duration
        self._uri = self._player.uri
        self._title = self._player.title
        self._album = self._player.album
        self._artist = self._player.artist

    def set_volume_level(self, volume: float) -> None:
        """Set the volume level."""
        self._player.volume = volume

    async def async_play_media(
        self, media_type: str, media_id: str, **kwargs: Any
    ) -> None:
        """Play media."""
        # Handle media_source
        if media_source.is_media_source_id(media_id):
            sourced_media = await media_source.async_resolve_media(
                self.hass, media_id, self.entity_id
            )
            media_id = sourced_media.url

        elif media_type != MEDIA_TYPE_MUSIC:
            _LOGGER.error("Invalid media type")
            return

        media_id = async_process_play_media_url(self.hass, media_id)

        await self.hass.async_add_executor_job(self._player.queue, media_id)

    def media_play(self) -> None:
        """Play."""
        self._player.play()

    def media_pause(self) -> None:
        """Pause."""
        self._player.pause()

    def media_next_track(self) -> None:
        """Next track."""
        self._player.next()

    @property
    def media_content_id(self):
        """Content ID of currently playing media."""
        return self._uri

    @property
    def content_type(self):
        """Content type of currently playing media."""
        return MEDIA_TYPE_MUSIC

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def volume_level(self):
        """Return the volume level."""
        return self._volume

    @property
    def state(self):
        """Return the state of the player."""
        return self._state

    @property
    def media_duration(self):
        """Duration of current playing media in seconds."""
        return self._duration

    @property
    def media_title(self):
        """Media title."""
        return self._title

    @property
    def media_artist(self):
        """Media artist."""
        return self._artist

    @property
    def media_album_name(self):
        """Media album."""
        return self._album

    async def async_browse_media(
        self, media_content_type: str | None = None, media_content_id: str | None = None
    ) -> BrowseMedia:
        """Implement the websocket media browsing helper."""
        return await media_source.async_browse_media(
            self.hass,
            media_content_id,
            content_filter=lambda item: item.media_content_type.startswith("audio/"),
        )
