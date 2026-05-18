"""Support for LED numbers."""

from collections.abc import Callable
from dataclasses import dataclass

from wled import Segment

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import ATTR_INTENSITY, ATTR_SPEED
from .coordinator import WLEDConfigEntry, WLEDDataUpdateCoordinator
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

    new_entities: list[WLEDEntity] = [
        WLEDNumber(coordinator, segment_id, desc)
        for desc in NUMBERS
        for segment_id in coordinator.segment_ids
    ]

    async_add_entities(new_entities)


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
        value_fn=lambda segment: int(segment.speed),
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
        self._segment = segment

        # The segment name defined in WLED is always used if available.
        segment_name = self.coordinator.data.state.segments[self._segment].name
        if segment_name:
            self._attr_translation_key = f"segment_named_{description.translation_key}"
            self._attr_translation_placeholders = {"segment_name": segment_name}
        elif segment != 0:
            self._attr_translation_key = f"segment_{description.translation_key}"
            self._attr_translation_placeholders = {"segment": str(segment)}

        self._attr_unique_id = (
            f"{coordinator.data.info.mac_address}_{description.key}_{segment}"
        )

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return (
            super().available and self._segment in self.coordinator.data.state.segments
        )

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
