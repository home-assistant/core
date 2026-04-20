"""Support for interfacing with Russound via RNET Protocol."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.media_player import (
    PLATFORM_SCHEMA as MEDIA_PLAYER_PLATFORM_SCHEMA,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import CONF_MODEL, CONF_SOURCES, DOMAIN, RNET_MODELS
from .coordinator import RussoundRNETConfigEntry, RussoundRNETCoordinator
from .entity import RussoundRNETEntity, command

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0

# Max volume level on RNET devices
_MAX_VOLUME = 50

ZONE_SCHEMA = vol.Schema({vol.Required(CONF_NAME): cv.string})

SOURCE_SCHEMA = vol.Schema({vol.Required(CONF_NAME): cv.string})

PLATFORM_SCHEMA = MEDIA_PLAYER_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_NAME): cv.string,
        vol.Required(CONF_PORT): cv.port,
        vol.Required("zones"): vol.Schema({cv.positive_int: ZONE_SCHEMA}),
        vol.Required("sources"): vol.All(cv.ensure_list, [SOURCE_SCHEMA]),
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Russound RNET platform from YAML (triggers import)."""
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=config
        )
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RussoundRNETConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Russound RNET media player from a config entry."""
    coordinator = entry.runtime_data
    model_key = entry.data.get(CONF_MODEL, "CAA66")
    model = RNET_MODELS[model_key]
    sources = entry.data.get(CONF_SOURCES, {})

    entities: list[RussoundRNETZone] = []
    for controller_id in range(1, model.max_controllers + 1):
        for zone_id in range(1, model.max_zones + 1):
            if (controller_id, zone_id) in coordinator.data:
                entities.append(
                    RussoundRNETZone(
                        coordinator,
                        controller_id,
                        zone_id,
                        sources,
                    )
                )

    async_add_entities(entities)


class RussoundRNETZone(RussoundRNETEntity, MediaPlayerEntity):
    """Representation of a Russound RNET zone."""

    _attr_supported_features = (
        MediaPlayerEntityFeature.VOLUME_MUTE
        | MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.TURN_ON
        | MediaPlayerEntityFeature.TURN_OFF
        | MediaPlayerEntityFeature.SELECT_SOURCE
    )

    def __init__(
        self,
        coordinator: RussoundRNETCoordinator,
        controller_id: int,
        zone_id: int,
        sources: dict[str, str],
    ) -> None:
        """Initialize the zone entity."""
        super().__init__(coordinator, controller_id, zone_id)
        self._sources = sources
        self._attr_source_list = [
            sources.get(str(i), f"Source {i}")
            for i in range(1, len(sources) + 1)
        ] or None
        entry = coordinator.config_entry
        self._attr_unique_id = f"{entry.entry_id}_{controller_id}_{zone_id}"

    @property
    def state(self) -> MediaPlayerState | None:
        """Return the state of the zone."""
        data = self.coordinator.data.get((self._controller_id, self._zone_id))
        if data is None:
            return None
        return MediaPlayerState.ON if data.power else MediaPlayerState.OFF

    @property
    def volume_level(self) -> float | None:
        """Return the volume level (0..1)."""
        data = self.coordinator.data.get((self._controller_id, self._zone_id))
        if data is None:
            return None
        return data.volume / _MAX_VOLUME

    @property
    def source(self) -> str | None:
        """Return the currently selected source."""
        data = self.coordinator.data.get((self._controller_id, self._zone_id))
        if data is None or not self._attr_source_list:
            return None
        index = data.source - 1
        if 0 <= index < len(self._attr_source_list):
            return self._attr_source_list[index]
        return None

    @command
    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level (0..1)."""
        device_volume = max(0, min(_MAX_VOLUME, int(volume * _MAX_VOLUME)))
        await self.coordinator.client.set_volume(
            self._controller_id, self._zone_id, device_volume
        )
        await self.coordinator.async_request_refresh()

    @command
    async def async_turn_on(self) -> None:
        """Turn the zone on."""
        await self.coordinator.client.set_zone_power(
            self._controller_id, self._zone_id, True
        )
        await self.coordinator.async_request_refresh()

    @command
    async def async_turn_off(self) -> None:
        """Turn the zone off."""
        await self.coordinator.client.set_zone_power(
            self._controller_id, self._zone_id, False
        )
        await self.coordinator.async_request_refresh()

    @command
    async def async_mute_volume(self, mute: bool) -> None:
        """Mute/unmute the zone."""
        await self.coordinator.client.toggle_mute(
            self._controller_id, self._zone_id
        )
        await self.coordinator.async_request_refresh()

    @command
    async def async_select_source(self, source: str) -> None:
        """Select the input source."""
        if self._attr_source_list and source in self._attr_source_list:
            index = self._attr_source_list.index(source) + 1
            await self.coordinator.client.select_source(
                self._controller_id, self._zone_id, index
            )
            await self.coordinator.async_request_refresh()

