"""Matter media player platform."""

from __future__ import annotations

from dataclasses import dataclass

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
from .entity import MatterEntity, MatterEntityDescription
from .helpers import get_matter
from .models import MatterDiscoverySchema


@dataclass(frozen=True, kw_only=True)
class MatterMediaPlayerEntityDescription(
    MediaPlayerEntityDescription, MatterEntityDescription
):
    """Matter media player entity description."""


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

    entity_description: MatterMediaPlayerEntityDescription
    _platform_translation_key = "media_player"
    _attr_supported_features = (
        MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.VOLUME_MUTE
        | MediaPlayerEntityFeature.VOLUME_STEP
    )
    _attr_volume_step = 0.01
    # No state in the Speaker endpoint as it is dedicated to volume control
    _attr_state = MediaPlayerState.ON

    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level."""
        # Read device max level (defaults to 254 if unavailable)
        max_level = self.get_matter_attribute_value(
            clusters.LevelControl.Attributes.MaxLevel
        )
        if max_level is None or max_level <= 0:
            max_level = 254

        if volume == 0:
            # If volume level is 0, turn off the volume
            await self.async_mute_volume(True)
            return
        # Unmute the volume if it was muted
        await self.async_mute_volume(False)

        # Convert HA volume level (0-1) to Matter level (0-254)
        # Matter uses 0-254 for volume levels, where 0 is off
        matter_volume_level = int(volume * max_level)
        await self.send_device_command(
            clusters.LevelControl.Commands.MoveToLevel(level=matter_volume_level)
        )

    async def async_mute_volume(self, mute: bool) -> None:
        """Mute or unmute the media player."""
        # OnOff attribute == True state means volume is on, so HA should show mute switch as off
        if mute:
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
        matter_volume = self.get_matter_attribute_value(
            clusters.LevelControl.Attributes.CurrentLevel
        )
        LOGGER.debug(
            "matter_volume: %s for %s",
            matter_volume,
            self.entity_id,
        )
        if matter_volume is None:
            # Attribute unavailable, cannot determine volume state
            return
        if matter_volume == 0:
            self._attr_is_volume_muted = True
        # Convert Matter CurrentLevel (0-254) to HA volume level (0-1)
        else:
            self._attr_is_volume_muted = False
            max_level = self.get_matter_attribute_value(
                clusters.LevelControl.Attributes.MaxLevel
            )
            if max_level is None or max_level <= 0:
                max_level = 254
            self._attr_volume_level = matter_volume / float(max_level)


# Discovery schema(s) to map Matter Attributes to HA entities
DISCOVERY_SCHEMAS = [
    MatterDiscoverySchema(
        platform=Platform.MEDIA_PLAYER,
        entity_description=MatterMediaPlayerEntityDescription(
            key="MatterMediaPlayer", name=None
        ),
        entity_class=MatterMediaPlayer,
        required_attributes=(
            clusters.OnOff.Attributes.OnOff,
            clusters.LevelControl.Attributes.CurrentLevel,
        ),
        optional_attributes=(clusters.LevelControl.Attributes.MaxLevel,),
        device_type=(device_types.Speaker,),
    ),
]
