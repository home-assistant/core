"""Support for interfacing with an instance of getchannels.com."""
from __future__ import annotations

from typing import Any

from pychannels import Channels
import voluptuous as vol

from homeassistant.components.media_player import (
    PLATFORM_SCHEMA,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
)
from homeassistant.components.media_player.const import (
    MEDIA_TYPE_CHANNEL,
    MEDIA_TYPE_EPISODE,
    MEDIA_TYPE_MOVIE,
    MEDIA_TYPE_TVSHOW,
)
from homeassistant.const import (
    ATTR_SECONDS,
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
    STATE_IDLE,
    STATE_PAUSED,
    STATE_PLAYING,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import SERVICE_SEEK_BACKWARD, SERVICE_SEEK_BY, SERVICE_SEEK_FORWARD

DATA_CHANNELS = "channels"
DEFAULT_NAME = "Channels"
DEFAULT_PORT = 57000

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Channels platform."""
    device = ChannelsPlayer(config[CONF_NAME], config[CONF_HOST], config[CONF_PORT])
    async_add_entities([device], True)

    platform = entity_platform.async_get_current_platform()

    platform.async_register_entity_service(
        SERVICE_SEEK_FORWARD,
        {},
        "seek_forward",
    )
    platform.async_register_entity_service(
        SERVICE_SEEK_BACKWARD,
        {},
        "seek_backward",
    )
    platform.async_register_entity_service(
        SERVICE_SEEK_BY,
        {vol.Required(ATTR_SECONDS): vol.Coerce(int)},
        "seek_by",
    )


class ChannelsPlayer(MediaPlayerEntity):
    """Representation of a Channels instance."""

    _attr_supported_features = (
        MediaPlayerEntityFeature.PLAY
        | MediaPlayerEntityFeature.PAUSE
        | MediaPlayerEntityFeature.STOP
        | MediaPlayerEntityFeature.VOLUME_MUTE
        | MediaPlayerEntityFeature.NEXT_TRACK
        | MediaPlayerEntityFeature.PREVIOUS_TRACK
        | MediaPlayerEntityFeature.PLAY_MEDIA
        | MediaPlayerEntityFeature.SELECT_SOURCE
    )

    def __init__(self, name, host, port):
        """Initialize the Channels app."""

        self._name = name
        self._host = host
        self._port = port

        self.client = Channels(self._host, self._port)

        self.status = None
        self.muted = None

        self.channel_number = None
        self.channel_name = None
        self.channel_image_url = None

        self.now_playing_title = None
        self.now_playing_episode_title = None
        self.now_playing_season_number = None
        self.now_playing_episode_number = None
        self.now_playing_summary = None
        self.now_playing_image_url = None

        self.favorite_channels = []

    def update_favorite_channels(self):
        """Update the favorite channels from the client."""
        self.favorite_channels = self.client.favorite_channels()

    def update_state(self, state_hash):
        """Update all the state properties with the passed in dictionary."""
        self.status = state_hash.get("status", "stopped")
        self.muted = state_hash.get("muted", False)

        channel_hash = state_hash.get("channel")
        np_hash = state_hash.get("now_playing")

        if channel_hash:
            self.channel_number = channel_hash.get("channel_number")
            self.channel_name = channel_hash.get("channel_name")
            self.channel_image_url = channel_hash.get("channel_image_url")
        else:
            self.channel_number = None
            self.channel_name = None
            self.channel_image_url = None

        if np_hash:
            self.now_playing_title = np_hash.get("title")
            self.now_playing_episode_title = np_hash.get("episode_title")
            self.now_playing_season_number = np_hash.get("season_number")
            self.now_playing_episode_number = np_hash.get("episode_number")
            self.now_playing_summary = np_hash.get("summary")
            self.now_playing_image_url = np_hash.get("image_url")
        else:
            self.now_playing_title = None
            self.now_playing_episode_title = None
            self.now_playing_season_number = None
            self.now_playing_episode_number = None
            self.now_playing_summary = None
            self.now_playing_image_url = None

    @property
    def name(self):
        """Return the name of the player."""
        return self._name

    @property
    def state(self):
        """Return the state of the player."""
        if self.status == "stopped":
            return STATE_IDLE

        if self.status == "paused":
            return STATE_PAUSED

        if self.status == "playing":
            return STATE_PLAYING

        return None

    def update(self) -> None:
        """Retrieve latest state."""
        self.update_favorite_channels()
        self.update_state(self.client.status())

    @property
    def source_list(self):
        """List of favorite channels."""
        sources = [channel["name"] for channel in self.favorite_channels]
        return sources

    @property
    def is_volume_muted(self):
        """Boolean if volume is currently muted."""
        return self.muted

    @property
    def media_content_id(self):
        """Content ID of current playing channel."""
        return self.channel_number

    @property
    def media_content_type(self):
        """Content type of current playing media."""
        return MEDIA_TYPE_CHANNEL

    @property
    def media_image_url(self):
        """Image url of current playing media."""
        if self.now_playing_image_url:
            return self.now_playing_image_url
        if self.channel_image_url:
            return self.channel_image_url

        return "https://getchannels.com/assets/img/icon-1024.png"

    @property
    def media_title(self):
        """Title of current playing media."""
        if self.state:
            return self.now_playing_title

        return None

    def mute_volume(self, mute: bool) -> None:
        """Mute (true) or unmute (false) player."""
        if mute != self.muted:
            response = self.client.toggle_muted()
            self.update_state(response)

    def media_stop(self) -> None:
        """Send media_stop command to player."""
        self.status = "stopped"
        response = self.client.stop()
        self.update_state(response)

    def media_play(self) -> None:
        """Send media_play command to player."""
        response = self.client.resume()
        self.update_state(response)

    def media_pause(self) -> None:
        """Send media_pause command to player."""
        response = self.client.pause()
        self.update_state(response)

    def media_next_track(self) -> None:
        """Seek ahead."""
        response = self.client.skip_forward()
        self.update_state(response)

    def media_previous_track(self) -> None:
        """Seek back."""
        response = self.client.skip_backward()
        self.update_state(response)

    def select_source(self, source: str) -> None:
        """Select a channel to tune to."""
        for channel in self.favorite_channels:
            if channel["name"] == source:
                response = self.client.play_channel(channel["number"])
                self.update_state(response)
                break

    def play_media(self, media_type: str, media_id: str, **kwargs: Any) -> None:
        """Send the play_media command to the player."""
        if media_type == MEDIA_TYPE_CHANNEL:
            response = self.client.play_channel(media_id)
            self.update_state(response)
        elif media_type in (MEDIA_TYPE_MOVIE, MEDIA_TYPE_EPISODE, MEDIA_TYPE_TVSHOW):
            response = self.client.play_recording(media_id)
            self.update_state(response)

    def seek_forward(self):
        """Seek forward in the timeline."""
        response = self.client.seek_forward()
        self.update_state(response)

    def seek_backward(self):
        """Seek backward in the timeline."""
        response = self.client.seek_backward()
        self.update_state(response)

    def seek_by(self, seconds):
        """Seek backward in the timeline."""
        response = self.client.seek(seconds)
        self.update_state(response)
