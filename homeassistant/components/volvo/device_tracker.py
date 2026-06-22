"""Volvo device tracker."""

from dataclasses import dataclass

from volvocarsapi.models import VolvoCarsApiBaseModel, VolvoCarsLocation

from homeassistant.components.device_tracker import (
    TrackerEntity,
    TrackerEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import VolvoConfigEntry
from .entity import VolvoEntity, VolvoEntityDescription

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class VolvoTrackerDescription(VolvoEntityDescription, TrackerEntityDescription):
    """Describes a Volvo Cars tracker entity."""


_DESCRIPTIONS: tuple[VolvoTrackerDescription, ...] = (
    VolvoTrackerDescription(
        key="location",
        api_field="location",
    ),
)


async def async_setup_entry(
    _: HomeAssistant,
    entry: VolvoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up tracker."""

    coordinators = entry.runtime_data.interval_coordinators
    async_add_entities(
        VolvoDeviceTracker(coordinator, description)
        for coordinator in coordinators
        for description in _DESCRIPTIONS
        if description.api_field in coordinator.data
    )


class VolvoDeviceTracker(VolvoEntity, TrackerEntity):
    """Volvo tracker."""

    entity_description: VolvoTrackerDescription

    def _update_state(self, api_field: VolvoCarsApiBaseModel | None) -> None:
        assert isinstance(api_field, VolvoCarsLocation)

        if api_field.geometry.coordinates and len(api_field.geometry.coordinates) > 1:
            self._attr_longitude = api_field.geometry.coordinates[0]
            self._attr_latitude = api_field.geometry.coordinates[1]
