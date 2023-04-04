"""Entity representing a Sonos number control."""
from __future__ import annotations

import logging
from typing import cast

from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import SONOS_CREATE_LEVELS
from .entity import SonosEntity
from .helpers import soco_error
from .speaker import SonosSpeaker

LEVEL_TYPES = {
    "audio_delay": (0, 5),
    "bass": (-10, 10),
    "treble": (-10, 10),
    "sub_gain": (-15, 15),
    "surround_level": (-15, 15),
    "music_surround_level": (-15, 15),
}

SocoFeatures = list[tuple[str, tuple[int, int]]]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Sonos number platform from a config entry."""

    def available_soco_attributes(speaker: SonosSpeaker) -> SocoFeatures:
        features: SocoFeatures = []
        for level_type, valid_range in LEVEL_TYPES.items():
            if (state := getattr(speaker.soco, level_type, None)) is not None:
                setattr(speaker, level_type, state)
                features.append((level_type, valid_range))
        return features

    async def _async_create_entities(speaker: SonosSpeaker) -> None:
        entities = []

        available_features = await hass.async_add_executor_job(
            available_soco_attributes, speaker
        )

        for level_type, valid_range in available_features:
            _LOGGER.debug(
                "Creating %s number control on %s", level_type, speaker.zone_name
            )
            entities.append(SonosLevelEntity(speaker, level_type, valid_range))
        async_add_entities(entities)

    config_entry.async_on_unload(
        async_dispatcher_connect(hass, SONOS_CREATE_LEVELS, _async_create_entities)
    )


class SonosLevelEntity(SonosEntity, NumberEntity):
    """Representation of a Sonos level entity."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self, speaker: SonosSpeaker, level_type: str, valid_range: tuple[int, int]
    ) -> None:
        """Initialize the level entity."""
        super().__init__(speaker)
        self._attr_unique_id = f"{self.soco.uid}-{level_type}"
        self._attr_name = level_type.replace("_", " ").capitalize()
        self.level_type = level_type
        self._attr_native_min_value, self._attr_native_max_value = valid_range

    async def _async_fallback_poll(self) -> None:
        """Poll the value if subscriptions are not working."""
        await self.hass.async_add_executor_job(self.poll_state)

    @soco_error()
    def poll_state(self) -> None:
        """Poll the device for the current state."""
        state = getattr(self.soco, self.level_type)
        setattr(self.speaker, self.level_type, state)

    @soco_error()
    def set_native_value(self, value: float) -> None:
        """Set a new value."""
        setattr(self.soco, self.level_type, value)

    @property
    def native_value(self) -> float:
        """Return the current value."""
        return cast(float, getattr(self.speaker, self.level_type))
