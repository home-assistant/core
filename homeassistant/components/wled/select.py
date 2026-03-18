"""Support for LED selects."""

from __future__ import annotations

from functools import partial

from wled import LiveDataOverride

from homeassistant.components.select import SelectEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import WLEDConfigEntry
from .coordinator import WLEDDataUpdateCoordinator
from .entity import WLEDEntity
from .helpers import wled_exception_handler

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WLEDConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up WLED select based on a config entry."""
    coordinator = entry.runtime_data

    async_add_entities(
        [
            WLEDLiveOverrideSelect(coordinator),
            WLEDPlaylistSelect(coordinator),
            WLEDPresetSelect(coordinator),
        ]
    )

    update_segments = partial(
        async_update_segments,
        coordinator,
        set(),
        async_add_entities,
    )
    coordinator.async_add_listener(update_segments)
    update_segments()


class WLEDLiveOverrideSelect(WLEDEntity, SelectEntity):
    """Defined a WLED Live Override select."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key = "live_override"

    def __init__(self, coordinator: WLEDDataUpdateCoordinator) -> None:
        """Initialize WLED ."""
        super().__init__(coordinator=coordinator)

        self._attr_unique_id = f"{coordinator.data.info.mac_address}_live_override"
        self._attr_options = [str(live.value) for live in LiveDataOverride]

    @property
    def current_option(self) -> str:
        """Return the current selected live override."""
        return str(self.coordinator.data.state.live_data_override.value)

    @wled_exception_handler
    async def async_select_option(self, option: str) -> None:
        """Set WLED state to the selected live override state."""
        await self.coordinator.wled.live(live=LiveDataOverride(int(option)))


class WLEDPresetSelect(WLEDEntity, SelectEntity):
    """Defined a WLED Preset select."""

    _attr_translation_key = "preset"

    def __init__(self, coordinator: WLEDDataUpdateCoordinator) -> None:
        """Initialize WLED ."""
        super().__init__(coordinator=coordinator)

        self._attr_unique_id = f"{coordinator.data.info.mac_address}_preset"
        sorted_values = sorted(
            coordinator.data.presets.values(), key=lambda preset: preset.name
        )
        self._attr_options = [preset.name for preset in sorted_values]

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return len(self.coordinator.data.presets) > 0 and super().available

    @property
    def current_option(self) -> str | None:
        """Return the current selected preset."""
        if not self.coordinator.data.state.preset_id:
            return None
        if preset := self.coordinator.data.presets.get(
            self.coordinator.data.state.preset_id
        ):
            return preset.name
        return None

    @wled_exception_handler
    async def async_select_option(self, option: str) -> None:
        """Set WLED segment to the selected preset."""
        await self.coordinator.wled.preset(preset=option)


class WLEDPlaylistSelect(WLEDEntity, SelectEntity):
    """Define a WLED Playlist select."""

    _attr_translation_key = "playlist"

    def __init__(self, coordinator: WLEDDataUpdateCoordinator) -> None:
        """Initialize WLED playlist."""
        super().__init__(coordinator=coordinator)

        self._attr_unique_id = f"{coordinator.data.info.mac_address}_playlist"
        sorted_values = sorted(
            coordinator.data.playlists.values(), key=lambda playlist: playlist.name
        )
        self._attr_options = [playlist.name for playlist in sorted_values]

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return len(self.coordinator.data.playlists) > 0 and super().available

    @property
    def current_option(self) -> str | None:
        """Return the currently selected playlist."""
        if not self.coordinator.data.state.playlist_id:
            return None
        if playlist := self.coordinator.data.playlists.get(
            self.coordinator.data.state.playlist_id
        ):
            return playlist.name
        return None

    @wled_exception_handler
    async def async_select_option(self, option: str) -> None:
        """Set WLED segment to the selected playlist."""
        await self.coordinator.wled.playlist(playlist=option)


class WLEDPaletteSelect(WLEDEntity, SelectEntity):
    """Defines a WLED Palette select."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key = "color_palette"
    _segment: int

    def __init__(self, coordinator: WLEDDataUpdateCoordinator, segment: int) -> None:
        """Initialize WLED ."""
        super().__init__(coordinator=coordinator)

        # Segment 0 uses a simpler name, which is more natural for when using
        # a single segment / using WLED with one big LED strip.
        if segment != 0:
            self._attr_translation_key = "segment_color_palette"
            self._attr_translation_placeholders = {"segment": str(segment)}

        self._attr_unique_id = f"{coordinator.data.info.mac_address}_palette_{segment}"
        sorted_values = sorted(
            coordinator.data.palettes.values(), key=lambda palette: palette.name
        )
        self._attr_options = [palette.name for palette in sorted_values]
        self._segment = segment

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        try:
            self.coordinator.data.state.segments[self._segment]
        except KeyError:
            return False

        return super().available

    @property
    def current_option(self) -> str | None:
        """Return the current selected color palette."""
        return self.coordinator.data.palettes[
            int(self.coordinator.data.state.segments[self._segment].palette_id)
        ].name

    @wled_exception_handler
    async def async_select_option(self, option: str) -> None:
        """Set WLED segment to the selected color palette."""
        await self.coordinator.wled.segment(segment_id=self._segment, palette=option)


@callback
def async_update_segments(
    coordinator: WLEDDataUpdateCoordinator,
    current_ids: set[int],
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Update segments."""
    segment_ids = {
        segment.segment_id
        for segment in coordinator.data.state.segments.values()
        if segment.segment_id is not None
    }

    new_entities: list[WLEDPaletteSelect] = []

    # Process new segments, add them to Home Assistant
    for segment_id in segment_ids - current_ids:
        current_ids.add(segment_id)
        new_entities.append(WLEDPaletteSelect(coordinator, segment_id))

    async_add_entities(new_entities)
