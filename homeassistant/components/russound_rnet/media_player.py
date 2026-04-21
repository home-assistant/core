"""Support for interfacing with Russound via RNET Protocol."""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.components.media_player import (
    PLATFORM_SCHEMA as MEDIA_PLAYER_PLATFORM_SCHEMA,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT, CONF_TYPE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import CONF_SOURCES, CONF_ZONES, DOMAIN, TYPE_TCP
from .coordinator import RussoundRNETConfigEntry, RussoundRNETCoordinator
from .entity import RussoundRNETEntity, command
from .repairs import async_create_deprecated_yaml_issue, async_create_yaml_import_issue

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
    """Set up the Russound RNET platform from YAML (triggers repair-based import)."""
    # Ensure top-level component is loaded so repairs platform is discoverable
    from homeassistant.setup import async_setup_component  # noqa: PLC0415

    await async_setup_component(hass, DOMAIN, {})

    # Check if a config entry already exists for this host/port
    host = config.get(CONF_HOST, "")
    port = config.get(CONF_PORT, 0)
    for entry in hass.config_entries.async_entries(DOMAIN):
        if (
            entry.data.get(CONF_TYPE) == TYPE_TCP
            and entry.data.get(CONF_HOST) == host
            and entry.data.get(CONF_PORT) == port
        ):
            # Config entry exists — tell user to remove YAML
            async_create_deprecated_yaml_issue(hass)
            return

    # No config entry — create fixable repair to complete import
    async_create_yaml_import_issue(hass, dict(config))


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RussoundRNETConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Russound RNET media player from a config entry."""
    coordinator = entry.runtime_data
    sources = entry.data.get(CONF_SOURCES, {})
    zones_config = entry.data.get(CONF_ZONES, {})

    # Build source list: only named sources, indexed by their slot number
    # Sources dict: {"1": "Sonos", "3": "Radio"} → sparse mapping
    source_list: list[tuple[int, str]] = sorted(
        ((int(k), v) for k, v in sources.items()), key=lambda x: x[0]
    )

    entities: list[RussoundRNETZone] = []

    # Only create entities for explicitly configured zones
    for zone_key, zone_name in zones_config.items():
        controller_id, zone_id = (int(x) for x in zone_key.split("_"))
        if (controller_id, zone_id) in coordinator.data:
            entities.append(
                RussoundRNETZone(
                    coordinator,
                    controller_id,
                    zone_id,
                    zone_name,
                    source_list,
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
        zone_name: str,
        source_list: list[tuple[int, str]],
    ) -> None:
        """Initialize the zone entity."""
        super().__init__(coordinator, controller_id, zone_id, zone_name)
        # source_list: sorted list of (slot_number, name) for active sources
        self._source_map = source_list
        self._attr_source_list = [name for _, name in source_list] or None
        # Reverse map: source name → slot number (1-based RNET index)
        self._source_to_index = {name: slot for slot, name in source_list}
        entry = coordinator.config_entry
        self._attr_unique_id = f"{entry.unique_id}_{controller_id}_{zone_id}"
        # RNET doesn't report mute state; track it locally
        self._attr_is_volume_muted = False

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
        if data is None:
            return None
        # data.source is 1-based RNET slot; find matching name
        for slot, name in self._source_map:
            if slot == data.source:
                return name
        return None

    @command
    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level (0..1)."""
        device_volume = max(0, min(_MAX_VOLUME, int(volume * _MAX_VOLUME)))
        await self.coordinator.client.set_volume(
            self._controller_id,
            self._zone_id,
            device_volume,
        )
        # Hardware auto-unmutes on volume change
        self._attr_is_volume_muted = False

    @command
    async def async_turn_on(self) -> None:
        """Turn the zone on."""
        await self.coordinator.client.set_zone_power(
            self._controller_id,
            self._zone_id,
            True,
        )

    @command
    async def async_turn_off(self) -> None:
        """Turn the zone off."""
        await self.coordinator.client.set_zone_power(
            self._controller_id,
            self._zone_id,
            False,
        )

    @command
    async def async_mute_volume(self, mute: bool) -> None:
        """Mute/unmute the zone."""
        if self._attr_is_volume_muted != mute:
            await self.coordinator.client.toggle_mute(
                self._controller_id,
                self._zone_id,
            )
            self._attr_is_volume_muted = mute

    @command
    async def async_select_source(self, source: str) -> None:
        """Select the input source."""
        if source in self._source_to_index:
            index = self._source_to_index[source]
            await self.coordinator.client.select_source(
                self._controller_id,
                self._zone_id,
                index,
            )
