"""Support for interfacing with an instance of getchannels.com."""
from pychannels import Channels
import voluptuous as vol

from homeassistant.components.media_player import PLATFORM_SCHEMA, MediaPlayerEntity
from homeassistant.components.media_player.const import (
    MEDIA_TYPE_CHANNEL,
    MEDIA_TYPE_EPISODE,
    MEDIA_TYPE_MOVIE,
    MEDIA_TYPE_TVSHOW,
    SUPPORT_NEXT_TRACK,
    SUPPORT_PAUSE,
    SUPPORT_PLAY,
    SUPPORT_PLAY_MEDIA,
    SUPPORT_PREVIOUS_TRACK,
    SUPPORT_SELECT_SOURCE,
    SUPPORT_STOP,
    SUPPORT_VOLUME_MUTE,
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
from homeassistant.helpers import config_validation as cv, entity_platform

from .const import SERVICE_SEEK_BACKWARD, SERVICE_SEEK_BY, SERVICE_SEEK_FORWARD

DEFAULT_NAME = "Channels"
DEFAULT_PORT = 57000

FEATURE_SUPPORT = (
    SUPPORT_PLAY
    | SUPPORT_PAUSE
    | SUPPORT_STOP
    | SUPPORT_VOLUME_MUTE
    | SUPPORT_NEXT_TRACK
    | SUPPORT_PREVIOUS_TRACK
    | SUPPORT_PLAY_MEDIA
    | SUPPORT_SELECT_SOURCE
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    }
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
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

    _attr_media_content_type = MEDIA_TYPE_CHANNEL
    _attr_supported_features = FEATURE_SUPPORT

    def __init__(self, name, host, port):
        """Initialize the Channels app."""

        self._attr_name = name
        self._host = host
        self._port = port
        self.client = Channels(host, port)
        self.status = None
        self.favorite_channels = []

    def update_favorite_channels(self):
        """Update the favorite channels from the client."""
        self.favorite_channels = self.client.favorite_channels()

    def update_state(self, state_hash):
        """Update all the state properties with the passed in dictionary."""
        self.status = state_hash.get("status", "stopped")
        self._attr_is_volume_muted = state_hash.get("muted", False)
        channel_hash = state_hash.get("channel")
        np_hash = state_hash.get("now_playing")
        channel_image_url = None
        if channel_hash:
            channel_image_url = channel_hash.get("channel_image_url")
        now_playing_title = now_playing_image_url = None
        if np_hash:
            now_playing_title = np_hash.get("title")
            now_playing_image_url = np_hash.get("image_url")
        self._attr_source_list = [channel["name"] for channel in self.favorite_channels]
        self._attr_media_title = now_playing_title if self._attr_state else None
        self._attr_media_image_url = (
            now_playing_image_url
            if now_playing_image_url
            else channel_image_url
            if channel_image_url
            else "https://getchannels.com/assets/img/icon-1024.png"
        )
        self._attr_state = None
        if self.status == "stopped":
            self._attr_state = STATE_IDLE
        elif self.status == "paused":
            self._attr_state = STATE_PAUSED
        elif self.status == "playing":
            self._attr_state = STATE_PLAYING

    def update(self):
        """Retrieve latest state."""
        self.update_favorite_channels()
        self.update_state(self.client.status())

    def mute_volume(self, mute):
        """Mute (true) or unmute (false) player."""
        if mute != self._attr_is_volume_muted:
            response = self.client.toggle_muted()
            self.update_state(response)

    def media_stop(self):
        """Send media_stop command to player."""
        self.status = "stopped"
        response = self.client.stop()
        self.update_state(response)

    def media_play(self):
        """Send media_play command to player."""
        response = self.client.resume()
        self.update_state(response)

    def media_pause(self):
        """Send media_pause command to player."""
        response = self.client.pause()
        self.update_state(response)

    def media_next_track(self):
        """Seek ahead."""
        response = self.client.skip_forward()
        self.update_state(response)

    def media_previous_track(self):
        """Seek back."""
        response = self.client.skip_backward()
        self.update_state(response)

    def select_source(self, source):
        """Select a channel to tune to."""
        for channel in self.favorite_channels:
            if channel["name"] == source:
                response = self.client.play_channel(channel["number"])
                self.update_state(response)
                break

    def play_media(self, media_type, media_id, **kwargs):
        """Send the play_media command to the player."""
        if media_type == MEDIA_TYPE_CHANNEL:
            response = self.client.play_channel(media_id)
            self.update_state(response)
        elif media_type in [MEDIA_TYPE_MOVIE, MEDIA_TYPE_EPISODE, MEDIA_TYPE_TVSHOW]:
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
