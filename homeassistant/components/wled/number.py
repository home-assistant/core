"""Support for LED numbers."""
from __future__ import annotations

from functools import partial

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import ATTR_INTENSITY, ATTR_SPEED, DOMAIN
from .coordinator import WLEDDataUpdateCoordinator
from .helpers import wled_exception_handler
from .models import WLEDEntity

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up WLED number based on a config entry."""
    coordinator: WLEDDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    update_segments = partial(
        async_update_segments,
        coordinator,
        set(),
        async_add_entities,
    )
    coordinator.async_add_listener(update_segments)
    update_segments()


NUMBERS = [
    NumberEntityDescription(
        key=ATTR_SPEED,
        name="Speed",
        icon="mdi:speedometer",
        entity_category=EntityCategory.CONFIG,
        native_step=1,
        native_min_value=0,
        native_max_value=255,
    ),
    NumberEntityDescription(
        key=ATTR_INTENSITY,
        name="Intensity",
        entity_category=EntityCategory.CONFIG,
        native_step=1,
        native_min_value=0,
        native_max_value=255,
    ),
]


class WLEDNumber(WLEDEntity, NumberEntity):
    """Defines a WLED speed number."""

    def __init__(
        self,
        coordinator: WLEDDataUpdateCoordinator,
        segment: int,
        description: NumberEntityDescription,
    ) -> None:
        """Initialize WLED ."""
        super().__init__(coordinator=coordinator)
        self.entity_description = description

        # Segment 0 uses a simpler name, which is more natural for when using
        # a single segment / using WLED with one big LED strip.
        self._attr_name = (
            f"{coordinator.data.info.name} Segment {segment} {description.name}"
        )
        if segment == 0:
            self._attr_name = f"{coordinator.data.info.name} {description.name}"

        self._attr_unique_id = (
            f"{coordinator.data.info.mac_address}_{description.key}_{segment}"
        )
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
    def native_value(self) -> float | None:
        """Return the current WLED segment number value."""
        return getattr(
            self.coordinator.data.state.segments[self._segment],
            self.entity_description.key,
        )

    @wled_exception_handler
    async def async_set_native_value(self, value: float) -> None:
        """Set the WLED segment value."""
        key = self.entity_description.key
        if key == ATTR_SPEED:
            await self.coordinator.wled.segment(
                segment_id=self._segment, speed=int(value)
            )
        elif key == ATTR_INTENSITY:
            await self.coordinator.wled.segment(
                segment_id=self._segment, intensity=int(value)
            )


@callback
def async_update_segments(
    coordinator: WLEDDataUpdateCoordinator,
    current_ids: set[int],
    async_add_entities,
) -> None:
    """Update segments."""
    segment_ids = {segment.segment_id for segment in coordinator.data.state.segments}

    new_entities = []

    # Process new segments, add them to Home Assistant
    for segment_id in segment_ids - current_ids:
        current_ids.add(segment_id)
        for desc in NUMBERS:
            new_entities.append(WLEDNumber(coordinator, segment_id, desc))

    if new_entities:
        async_add_entities(new_entities)
