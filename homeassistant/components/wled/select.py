"""Support for LED selects."""
from __future__ import annotations

from functools import partial

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity_registry import (
    async_get_registry as async_get_entity_registry,
)

from .const import DOMAIN
from .coordinator import WLEDDataUpdateCoordinator
from .helpers import wled_exception_handler
from .models import WLEDEntity

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up WLED select based on a config entry."""
    coordinator: WLEDDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    update_segments = partial(
        async_update_segments,
        entry,
        coordinator,
        {},
        async_add_entities,
    )
    coordinator.async_add_listener(update_segments)
    update_segments()


class WLEDPaletteSelect(WLEDEntity, SelectEntity):
    """Defines a WLED Palette select."""

    _attr_icon = "mdi:palette-outline"
    _segment: int

    def __init__(self, coordinator: WLEDDataUpdateCoordinator, segment: int) -> None:
        """Initialize WLED ."""
        super().__init__(coordinator=coordinator)

        # If this is the one and only segment, use a simpler name
        self._attr_name = (
            f"{coordinator.data.info.name} Segment {segment} Color Palette"
        )
        if len(coordinator.data.state.segments) == 1:
            self._attr_name = f"{coordinator.data.info.name} Color Palette"

        self._attr_unique_id = f"{coordinator.data.info.mac_address}_{segment}"
        self._attr_options = [
            palette.name for palette in self.coordinator.data.palettes
        ]
        self._segment = segment

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        try:
            self.coordinator.data.state.segments[self._segment]
        except IndexError:
            return False

        return super().available

    @property
    def current_option(self) -> str | None:
        """Return the current selected color palette."""
        return self.coordinator.data.state.segments[self._segment].palette.name

    @wled_exception_handler
    async def async_select_option(self, option: str) -> None:
        """Set WLED segment to the selected color palette."""
        await self.coordinator.wled.segment(segment_id=self._segment, palette=option)


@callback
def async_update_segments(
    entry: ConfigEntry,
    coordinator: WLEDDataUpdateCoordinator,
    current: dict[int, WLEDPaletteSelect],
    async_add_entities,
) -> None:
    """Update segments."""
    segment_ids = {segment.segment_id for segment in coordinator.data.state.segments}
    current_ids = set(current)

    new_entities = []

    # Process new segments, add them to Home Assistant
    for segment_id in segment_ids - current_ids:
        current[segment_id] = WLEDPaletteSelect(coordinator, segment_id)
        new_entities.append(current[segment_id])

    if new_entities:
        async_add_entities(new_entities)

    # Process deleted segments, remove them from Home Assistant
    for segment_id in current_ids - segment_ids:
        coordinator.hass.async_create_task(
            async_remove_entity(segment_id, coordinator, current)
        )


async def async_remove_entity(
    index: int,
    coordinator: WLEDDataUpdateCoordinator,
    current: dict[int, WLEDPaletteSelect],
) -> None:
    """Remove WLED segment from Home Assistant."""
    entity = current[index]
    await entity.async_remove(force_remove=True)
    registry = await async_get_entity_registry(coordinator.hass)
    if entity.entity_id in registry.entities:
        registry.async_remove(entity.entity_id)
    del current[index]
