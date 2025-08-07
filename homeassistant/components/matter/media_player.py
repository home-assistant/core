"""Matter media player platform."""

from __future__ import annotations

from typing import Any

from chip.clusters import Objects as clusters
from matter_server.client.models import device_types

from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityDescription,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import MatterEntity
from .helpers import get_matter
from .models import MatterDiscoverySchema


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Matter media player platform from Config Entry."""
    matter = get_matter(hass)
    matter.register_platform_handler(Platform.MEDIA_PLAYER, async_add_entities)


class MatterMediaPlayer(MatterEntity, MediaPlayerEntity):
    """Representation of a Matter Media Player entity."""

    entity_description: MediaPlayerEntityDescription
    _platform_translation_key = "mediaplayer"

    async def async_stop(self, **kwargs: Any) -> None:
        """Stop the media player."""

    async def async_start(self) -> None:
        """Start the media player."""

    async def async_pause(self) -> None:
        """Pause the media player."""
        # await self.send_device_command(clusters.RvcOperationalState.Commands.Pause())

    @callback
    def _update_from_device(self) -> None:
        """Update from device."""
        self._calculate_features()
        # state: VacuumActivity | None = None
        # self._attr_activity = state
        self._attr_volume_level = 50  # Example volume level
        self._attr_is_volume_muted = False  # Example mute state
        self._attr_state = MediaPlayerState.OFF

    @callback
    def _calculate_features(self) -> None:
        """Calculate features for HA MediaPlayer platform."""
        supported_features = (
            MediaPlayerEntityFeature.TURN_ON
            | MediaPlayerEntityFeature.TURN_OFF
            | MediaPlayerEntityFeature.VOLUME_SET
            | MediaPlayerEntityFeature.VOLUME_MUTE
        )
        self._attr_supported_features = supported_features


# Discovery schema(s) to map Matter Attributes to HA entities
DISCOVERY_SCHEMAS = [
    MatterDiscoverySchema(
        platform=Platform.MEDIA_PLAYER,
        entity_description=MediaPlayerEntityDescription(
            key="MatterMediaPlayer", name=None
        ),
        entity_class=MatterMediaPlayer,
        required_attributes=(
            clusters.OnOff.Attributes.OnOff,
            clusters.LevelControl.Attributes.CurrentLevel,
        ),
        device_type=(device_types.Speaker,),
    ),
]
