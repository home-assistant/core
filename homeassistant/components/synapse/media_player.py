import logging

from homeassistant.components.mediaplayer import MediaPlayerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import callback, HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .base_entity import SynapseBaseEntity
from .bridge import SynapseBridge
from .const import DOMAIN, SynapseMediaPlayerDefinition

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Setup the router platform."""
    bridge: SynapseBridge = hass.data[DOMAIN][config_entry.entry_id]
    entities = bridge.config_data.get("mediaplayer")
    if entities is not None:
      async_add_entities(SynapseMediaPlayer(hass, bridge, entity) for entity in entities)

class SynapseMediaPlayer(SynapseBaseEntity, MediaPlayerEntity):
    def __init__(
        self,
        hass: HomeAssistant,
        hub: SynapseBridge,
        entity: SynapseMediaPlayerDefinition,
    ):
        super().__init__(hass, hub, entity)
        self.logger = logging.getLogger(__name__)

    @property
    def app_id(self):
        return self.entity.get("app_id")

    @property
    def app_name(self):
        return self.entity.get("app_name")

    @property
    def device_class(self):
        return self.entity.get("device_class")

    @property
    def group_members(self):
        return self.entity.get("group_members")

    @property
    def is_volume_muted(self):
        return self.entity.get("is_volume_muted")

    @property
    def media_album_artist(self):
        return self.entity.get("media_album_artist")

    @property
    def media_album_name(self):
        return self.entity.get("media_album_name")

    @property
    def media_artist(self):
        return self.entity.get("media_artist")

    @property
    def media_channel(self):
        return self.entity.get("media_channel")

    @property
    def media_content_id(self):
        return self.entity.get("media_content_id")

    @property
    def media_content_type(self):
        return self.entity.get("media_content_type")

    @property
    def media_duration(self):
        return self.entity.get("media_duration")

    @property
    def media_episode(self):
        return self.entity.get("media_episode")

    @property
    def media_image_hash(self):
        return self.entity.get("media_image_hash")

    @property
    def media_image_remotely_accessible(self):
        return self.entity.get("media_image_remotely_accessible")

    @property
    def media_image_url(self):
        return self.entity.get("media_image_url")

    @property
    def media_playlist(self):
        return self.entity.get("media_playlist")

    @property
    def media_position(self):
        return self.entity.get("media_position")

    @property
    def media_position_updated_at(self):
        return self.entity.get("media_position_updated_at")

    @property
    def media_season(self):
        return self.entity.get("media_season")

    @property
    def media_series_title(self):
        return self.entity.get("media_series_title")

    @property
    def media_title(self):
        return self.entity.get("media_title")

    @property
    def media_track(self):
        return self.entity.get("media_track")

    @property
    def repeat(self):
        return self.entity.get("repeat")

    @property
    def shuffle(self):
        return self.entity.get("shuffle")

    @property
    def sound_mode(self):
        return self.entity.get("sound_mode")

    @property
    def sound_mode_list(self):
        return self.entity.get("sound_mode_list")

    @property
    def source(self):
        return self.entity.get("source")

    @property
    def source_list(self):
        return self.entity.get("source_list")

    @property
    def supported_features(self):
        return self.entity.get("supported_features")

    @property
    def volume_level(self):
        return self.entity.get("volume_level")

    @property
    def volume_step(self):
        return self.entity.get("volume_step")

    @callback
    async def async_play_media(
        self, media_content_type: str, media_content_id: str, **kwargs
    ) -> None:
        """Proxy the request to play media."""
        self.hass.bus.async_fire(
            self.bridge.event_name("play_media"),
            {
                "unique_id": self.entity.get("unique_id"),
                "media_content_type": media_content_type,
                "media_content_id": media_content_id,
                **kwargs,
            },
        )

    @callback
    async def async_select_sound_mode(self, sound_mode: str, **kwargs) -> None:
        """Proxy the request to select a sound mode."""
        self.hass.bus.async_fire(
            self.bridge.event_name("select_sound_mode"),
            {
                "unique_id": self.entity.get("unique_id"),
                "sound_mode": sound_mode,
                **kwargs,
            },
        )

    @callback
    async def async_select_source(self, source: str, **kwargs) -> None:
        """Proxy the request to select a source."""
        self.hass.bus.async_fire(
            self.bridge.event_name("select_source"),
            {"unique_id": self.entity.get("unique_id"), "source": source, **kwargs},
        )
