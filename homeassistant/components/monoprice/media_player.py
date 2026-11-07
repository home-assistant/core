"""Support for interfacing with Monoprice 6 zone home audio controller."""

from collections.abc import Callable
import logging
from typing import Any, override

from pymonoprice import ZoneStatus

from homeassistant import core
from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.const import CONF_PORT
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import MonopriceConfigEntry
from .const import CONF_SOURCES, DOMAIN
from .coordinator import ZONE_IDS, MonopriceCoordinator

_LOGGER = logging.getLogger(__name__)

MAX_VOLUME = 38
PARALLEL_UPDATES = 1


@core.callback
def _get_sources_from_dict(data):
    sources_config = data[CONF_SOURCES]

    source_id_name = {int(index): name for index, name in sources_config.items()}

    source_name_id = {v: k for k, v in source_id_name.items()}

    source_names = sorted(source_name_id.keys(), key=lambda v: source_name_id[v])

    return [source_id_name, source_name_id, source_names]


@core.callback
def _get_sources(config_entry):
    if CONF_SOURCES in config_entry.options:
        data = config_entry.options
    else:
        data = config_entry.data
    return _get_sources_from_dict(data)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: MonopriceConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Monoprice 6-zone amplifier platform."""
    port = config_entry.data[CONF_PORT]

    sources = _get_sources(config_entry)
    runtime_data = config_entry.runtime_data

    entities = []
    for zone_id in ZONE_IDS:
        _LOGGER.debug("Adding zone %d for port %s", zone_id, port)
        entities.append(
            MonopriceZone(
                runtime_data.coordinator,
                sources,
                config_entry.entry_id,
                zone_id,
                runtime_data.discovered_zones is None
                or zone_id < 20
                or zone_id in runtime_data.discovered_zones,
            )
        )

    async_add_entities(entities)


class MonopriceZone(CoordinatorEntity[MonopriceCoordinator], MediaPlayerEntity):
    """Representation of a Monoprice amplifier zone."""

    _attr_device_class = MediaPlayerDeviceClass.RECEIVER
    _attr_supported_features = (
        MediaPlayerEntityFeature.VOLUME_MUTE
        | MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.VOLUME_STEP
        | MediaPlayerEntityFeature.TURN_ON
        | MediaPlayerEntityFeature.TURN_OFF
        | MediaPlayerEntityFeature.SELECT_SOURCE
    )
    _attr_has_entity_name = True
    _attr_name = None
    _attr_volume_step = 1 / MAX_VOLUME

    def __init__(
        self,
        coordinator: MonopriceCoordinator,
        sources,
        namespace,
        zone_id: int,
        enabled_default: bool,
    ) -> None:
        """Initialize new zone."""
        super().__init__(coordinator, context=zone_id)
        self._monoprice = coordinator.client
        self._attr_entity_registry_enabled_default = enabled_default
        # dict source_id -> source name
        self._source_id_name = sources[0]
        # dict source name -> source_id
        self._source_name_id = sources[1]
        # ordered list of all source names
        self._attr_source_list = sources[2]
        self._zone_id = zone_id
        self._attr_unique_id = f"{namespace}_{self._zone_id}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._attr_unique_id)},
            manufacturer="Monoprice",
            model="6-Zone Amplifier",
            name=f"Zone {self._zone_id}",
        )

        self._snapshot: ZoneStatus | None = None
        self._update_from_status()

    @callback
    def _update_from_status(self) -> None:
        """Take the state from the latest status of the zone."""
        if (state := self.coordinator.data.get(self._zone_id)) is None:
            return
        self._attr_state = MediaPlayerState.ON if state.power else MediaPlayerState.OFF
        self._attr_volume_level = state.volume / MAX_VOLUME
        self._attr_is_volume_muted = state.mute
        self._attr_source = self._source_id_name.get(state.source)

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Handle a new status of the zone."""
        self._update_from_status()
        super()._handle_coordinator_update()

    @property
    @override
    def available(self) -> bool:
        """Return whether this zone answered its last poll."""
        return (
            super().available and self.coordinator.data.get(self._zone_id) is not None
        )

    @property
    @override
    def media_title(self) -> str | None:
        """Return the current source as medial title."""
        return self.source

    async def _async_send(self, command: Callable[..., Any], *args: Any) -> None:
        """Send a command to the amplifier, then read back the zone."""
        await self.coordinator.async_command(self._zone_id, command, *args)

    async def async_snapshot(self) -> None:
        """Save zone's current state."""
        self._snapshot = await self.coordinator.async_snapshot(self._zone_id)

    async def async_restore(self) -> None:
        """Restore saved state."""
        if self._snapshot:
            await self._async_send(self._monoprice.restore_zone, self._snapshot)

    @override
    async def async_select_source(self, source: str) -> None:
        """Set input source."""
        if source not in self._source_name_id:
            return
        idx = self._source_name_id[source]
        await self._async_send(self._monoprice.set_source, self._zone_id, idx)

    @override
    async def async_turn_on(self) -> None:
        """Turn the media player on."""
        await self._async_send(self._monoprice.set_power, self._zone_id, True)

    @override
    async def async_turn_off(self) -> None:
        """Turn the media player off."""
        await self._async_send(self._monoprice.set_power, self._zone_id, False)

    @override
    async def async_mute_volume(self, mute: bool) -> None:
        """Mute (true) or unmute (false) media player."""
        await self._async_send(self._monoprice.set_mute, self._zone_id, mute)

    @override
    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level, range 0..1."""
        await self._async_send(
            self._monoprice.set_volume, self._zone_id, round(volume * MAX_VOLUME)
        )
