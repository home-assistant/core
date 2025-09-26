"""Support for LED numbers."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from functools import partial

from wled import Segment

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import WLEDConfigEntry
from .const import ATTR_INTENSITY, ATTR_SPEED
from .coordinator import WLEDDataUpdateCoordinator
from .entity import WLEDEntity
from .helpers import wled_exception_handler

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WLEDConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up WLED number based on a config entry."""
    coordinator = entry.runtime_data

    update_segments = partial(
        async_update_segments,
        coordinator,
        set(),
        async_add_entities,
    )
    coordinator.async_add_listener(update_segments)
    update_segments()


@dataclass(frozen=True, kw_only=True)
class WLEDNumberEntityDescription(NumberEntityDescription):
    """Class describing WLED number entities."""

    value_fn: Callable[[Segment], int | None]


NUMBERS = [
    WLEDNumberEntityDescription(
        key=ATTR_SPEED,
        translation_key="speed",
        entity_category=EntityCategory.CONFIG,
        native_step=1,
        native_min_value=0,
        native_max_value=255,
        value_fn=lambda segment: segment.speed,
    ),
    WLEDNumberEntityDescription(
        key=ATTR_INTENSITY,
        translation_key="intensity",
        entity_category=EntityCategory.CONFIG,
        native_step=1,
        native_min_value=0,
        native_max_value=255,
        value_fn=lambda segment: int(segment.intensity),
    ),
]


class WLEDNumber(WLEDEntity, NumberEntity):
    """Defines a WLED speed number."""

    entity_description: WLEDNumberEntityDescription

    def __init__(
        self,
        coordinator: WLEDDataUpdateCoordinator,
        segment: int,
        description: WLEDNumberEntityDescription,
    ) -> None:
        """Initialize WLED ."""
        super().__init__(coordinator=coordinator)
        self.entity_description = description

        # Segment 0 uses a simpler name, which is more natural for when using
        # a single segment / using WLED with one big LED strip.
        if segment != 0:
            self._attr_translation_key = f"segment_{description.translation_key}"
            self._attr_translation_placeholders = {"segment": str(segment)}

        self._attr_unique_id = (
            f"{coordinator.data.info.mac_address}_{description.key}_{segment}"
        )
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
    def native_value(self) -> float | None:
        """Return the current WLED segment number value."""
        return self.entity_description.value_fn(
            self.coordinator.data.state.segments[self._segment]
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
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Update segments."""
    segment_ids = {
        segment.segment_id
        for segment in coordinator.data.state.segments.values()
        if segment.segment_id is not None
    }

    new_entities: list[WLEDNumber] = []

    # Process new segments, add them to Home Assistant
    for segment_id in segment_ids - current_ids:
        current_ids.add(segment_id)
        new_entities.extend(
            WLEDNumber(coordinator, segment_id, desc) for desc in NUMBERS
        )

    async_add_entities(new_entities)
