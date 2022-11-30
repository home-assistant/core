"""Support for LED selects."""
from __future__ import annotations

from functools import partial

from wled import Live, Playlist, Preset

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DEVICE_CLASS_WLED_LIVE_OVERRIDE, DOMAIN
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

    _attr_device_class = DEVICE_CLASS_WLED_LIVE_OVERRIDE
    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:theater"
    _attr_name = "Live override"

    def __init__(self, coordinator: WLEDDataUpdateCoordinator) -> None:
        """Initialize WLED ."""
        super().__init__(coordinator=coordinator)

        self._attr_unique_id = f"{coordinator.data.info.mac_address}_live_override"
        self._attr_options = [str(live.value) for live in Live]

    @property
    def current_option(self) -> str:
        """Return the current selected live override."""
        return str(self.coordinator.data.state.lor.value)

    @wled_exception_handler
    async def async_select_option(self, option: str) -> None:
        """Set WLED state to the selected live override state."""
        await self.coordinator.wled.live(live=Live(int(option)))


class WLEDPresetSelect(WLEDEntity, SelectEntity):
    """Defined a WLED Preset select."""

    _attr_icon = "mdi:playlist-play"
    _attr_name = "Preset"

    def __init__(self, coordinator: WLEDDataUpdateCoordinator) -> None:
        """Initialize WLED ."""
        super().__init__(coordinator=coordinator)

        self._attr_unique_id = f"{coordinator.data.info.mac_address}_preset"
        self._attr_options = [preset.name for preset in self.coordinator.data.presets]

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return len(self.coordinator.data.presets) > 0 and super().available

    @property
    def current_option(self) -> str | None:
        """Return the current selected preset."""
        if not isinstance(self.coordinator.data.state.preset, Preset):
            return None
        return self.coordinator.data.state.preset.name

    @wled_exception_handler
    async def async_select_option(self, option: str) -> None:
        """Set WLED segment to the selected preset."""
        await self.coordinator.wled.preset(preset=option)


class WLEDPlaylistSelect(WLEDEntity, SelectEntity):
    """Define a WLED Playlist select."""

    _attr_icon = "mdi:play-speed"
    _attr_name = "Playlist"

    def __init__(self, coordinator: WLEDDataUpdateCoordinator) -> None:
        """Initialize WLED playlist."""
        super().__init__(coordinator=coordinator)

        self._attr_unique_id = f"{coordinator.data.info.mac_address}_playlist"
        self._attr_options = [
            playlist.name for playlist in self.coordinator.data.playlists
        ]

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return len(self.coordinator.data.playlists) > 0 and super().available

    @property
    def current_option(self) -> str | None:
        """Return the currently selected playlist."""
        if not isinstance(self.coordinator.data.state.playlist, Playlist):
            return None
        return self.coordinator.data.state.playlist.name

    @wled_exception_handler
    async def async_select_option(self, option: str) -> None:
        """Set WLED segment to the selected playlist."""
        await self.coordinator.wled.playlist(playlist=option)


class WLEDPaletteSelect(WLEDEntity, SelectEntity):
    """Defines a WLED Palette select."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:palette-outline"
    _attr_name = "Color palette"
    _segment: int

    def __init__(self, coordinator: WLEDDataUpdateCoordinator, segment: int) -> None:
        """Initialize WLED ."""
        super().__init__(coordinator=coordinator)

        # Segment 0 uses a simpler name, which is more natural for when using
        # a single segment / using WLED with one big LED strip.
        if segment != 0:
            self._attr_name = f"Segment {segment} color palette"

        self._attr_unique_id = f"{coordinator.data.info.mac_address}_palette_{segment}"
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
    coordinator: WLEDDataUpdateCoordinator,
    current_ids: set[int],
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Update segments."""
    segment_ids = {segment.segment_id for segment in coordinator.data.state.segments}

    new_entities: list[WLEDPaletteSelect] = []

    # Process new segments, add them to Home Assistant
    for segment_id in segment_ids - current_ids:
        current_ids.add(segment_id)
        new_entities.append(WLEDPaletteSelect(coordinator, segment_id))

    async_add_entities(new_entities)
