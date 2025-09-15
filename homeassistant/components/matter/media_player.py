"""Matter media player platform."""

from __future__ import annotations

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

from .const import LOGGER
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

    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level."""
        if volume == 0:
            # If volume level is 0, turn off the volume
            await self.async_mute_volume(True)
            return
        # Unmute the volume if it was muted
        await self.async_mute_volume(False)

        # Convert HA volume level (0-1) to Matter level (0-254)
        # Matter uses 0-254 for volume levels, where 0 is off
        matter_volume_level = int(volume * 254)
        await self.send_device_command(
            clusters.LevelControl.Commands.MoveToLevel(level=matter_volume_level)
        )

    async def async_mute_volume(self, mute: bool) -> None:
        """Mute or unmute the media player."""
        # OnOff attribute == True state means volume is on, so HA should show mute switch as off
        if mute:
            # Save current volume before muting to be able to restore it
            current_volume = self._attr_volume_level or 1
            matter_volume_level = int(current_volume * 254)
            await self.write_attribute(
                matter_volume_level, clusters.LevelControl.Attributes.OnLevel
            )
            # Send Matter Off command
            await self.send_device_command(
                clusters.OnOff.Commands.Off(),
            )
        # OnOff attribute == False means volume is off (muted), so HA should show mute switch as on
        else:
            await self.send_device_command(
                clusters.OnOff.Commands.On(),
            )

    @callback
    def _update_from_device(self) -> None:
        """Update from device."""
        self._calculate_features()
        matter_volume = self.get_matter_attribute_value(
            clusters.LevelControl.Attributes.CurrentLevel
        )
        LOGGER.debug(
            "matter_volume: %f for %s",
            matter_volume,
            self.entity_id,
        )
        if matter_volume == 0:
            self._attr_is_volume_muted = True
        # Convert Matter CurrentLevel (0-254) to HA volume level (0-1)
        else:
            self._attr_is_volume_muted = False
            self._attr_volume_level = matter_volume / 254.0
        # No state in the Speaker endpoint as it dedicated to volume control
        self._attr_state = MediaPlayerState.ON

    @callback
    def _calculate_features(self) -> None:
        """Calculate features for HA MediaPlayer platform."""
        supported_features = (
            MediaPlayerEntityFeature.VOLUME_SET
            | MediaPlayerEntityFeature.VOLUME_MUTE
            | MediaPlayerEntityFeature.VOLUME_STEP
        )
        self._attr_supported_features = supported_features
        self._attr_volume_step = 0.01  # Matter uses 1-254, so step can be small


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
            clusters.LevelControl.Attributes.OnLevel,
        ),
        device_type=(device_types.Speaker,),
    ),
]
