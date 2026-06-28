"""The tests for vacuum platforms."""

from typing import Any

from homeassistant.components.vacuum import (
    Segment,
    StateVacuumEntity,
    VacuumActivity,
    VacuumEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from tests.common import MockEntity


class MockVacuum(MockEntity, StateVacuumEntity):
    """Mock vacuum class."""

    _attr_supported_features = (
        VacuumEntityFeature.PAUSE
        | VacuumEntityFeature.STOP
        | VacuumEntityFeature.RETURN_HOME
        | VacuumEntityFeature.FAN_SPEED
        | VacuumEntityFeature.BATTERY
        | VacuumEntityFeature.CLEAN_SPOT
        | VacuumEntityFeature.MAP
        | VacuumEntityFeature.STATE
        | VacuumEntityFeature.START
    )
    _attr_battery_level = 99
    _attr_fan_speed_list = ["slow", "fast"]

    def __init__(self, **values: Any) -> None:
        """Initialize a mock vacuum entity."""
        super().__init__(**values)
        self._attr_activity = VacuumActivity.DOCKED
        self._attr_fan_speed = "slow"

    def stop(self, **kwargs: Any) -> None:
        """Stop cleaning."""
        self._attr_activity = VacuumActivity.IDLE

    def return_to_base(self, **kwargs: Any) -> None:
        """Return to base."""
        self._attr_activity = VacuumActivity.RETURNING

    def clean_spot(self, **kwargs: Any) -> None:
        """Clean a spot."""
        self._attr_activity = VacuumActivity.CLEANING

    def set_fan_speed(self, fan_speed: str, **kwargs: Any) -> None:
        """Set the fan speed."""
        self._attr_fan_speed = fan_speed

    def start(self) -> None:
        """Start cleaning."""
        self._attr_activity = VacuumActivity.CLEANING

    def pause(self) -> None:
        """Pause cleaning."""
        self._attr_activity = VacuumActivity.PAUSED


async def help_async_setup_entry_init(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> bool:
    """Set up test config entry."""
    await hass.config_entries.async_forward_entry_setups(
        config_entry, [Platform.VACUUM]
    )
    return True


async def help_async_unload_entry(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> bool:
    """Unload test config emntry."""
    return await hass.config_entries.async_unload_platforms(
        config_entry, [Platform.VACUUM]
    )


SEGMENTS = [
    Segment(id="seg_1", name="Kitchen"),
    Segment(id="seg_2", name="Living Room"),
    Segment(id="seg_3", name="Bedroom"),
    Segment(id="seg_4", name="Bedroom", group="Upstairs"),
    Segment(id="seg_5", name="Bathroom", group="Upstairs"),
]


class MockVacuumWithCleanArea(MockEntity, StateVacuumEntity):
    """Mock vacuum with clean_area support."""

    _attr_supported_features = (
        VacuumEntityFeature.STATE
        | VacuumEntityFeature.START
        | VacuumEntityFeature.CLEAN_AREA
    )

    def __init__(
        self,
        segments: list[Segment] | None = None,
        unique_id: str = "mock_vacuum_unique_id",
        **values: Any,
    ) -> None:
        """Initialize a mock vacuum entity."""
        super().__init__(**values)
        self._attr_unique_id = unique_id
        self._attr_activity = VacuumActivity.DOCKED
        self.segments = segments if segments is not None else SEGMENTS
        self.clean_segments_calls: list[tuple[list[str], dict[str, Any]]] = []

    def start(self) -> None:
        """Start cleaning."""
        self._attr_activity = VacuumActivity.CLEANING

    async def async_get_segments(self) -> list[Segment]:
        """Get the segments that can be cleaned."""
        return self.segments

    async def async_clean_segments(self, segment_ids: list[str], **kwargs: Any) -> None:
        """Perform an area clean."""
        self.clean_segments_calls.append((segment_ids, kwargs))
        self._attr_activity = VacuumActivity.CLEANING
