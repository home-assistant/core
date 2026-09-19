"""Metadata sensors for Immich Frames."""

from collections.abc import Callable
from typing import Any, override

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .coordinator import ImmichFramesConfigEntry, ImmichFramesDataUpdateCoordinator
from .entity import ImmichFramesEntity

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ImmichFramesConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up metadata sensors."""
    coordinator = entry.runtime_data
    async_add_entities(
        PhotoSensor(coordinator, key, value)
        for key, value in (
            ("photo_date", _photo_date),
            ("photo_location", _photo_location),
            ("photo_people", _photo_people),
            ("matching_assets", lambda data: data.matching_assets),
            ("frame_status", lambda data: data.status),
        )
    )


def _photo_date(data) -> str:
    """Return the source capture date."""
    return data.asset.local_datetime.strftime("%-d %B, %Y")


def _photo_location(data) -> str | None:
    """Return the source location."""
    exif = data.asset.exif_info
    if exif is None:
        return None
    return (
        ", ".join(value for value in (exif.city, exif.state, exif.country) if value)
        or None
    )


def _names(values: list[Any]) -> str | None:
    """Return readable names from Immich relationship objects."""
    names = [
        value.name if hasattr(value, "name") else str(value)
        for value in values
        if getattr(value, "name", value)
    ]
    return ", ".join(names) or None


def _photo_people(data) -> str | None:
    """Return recognized people."""
    return _names(data.asset.people)


class PhotoSensor(ImmichFramesEntity, SensorEntity):
    """Expose metadata for the currently displayed photo."""

    def __init__(
        self,
        coordinator: ImmichFramesDataUpdateCoordinator,
        key: str,
        value: Callable[[Any], Any],
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, key)
        self._value = value
        self._attr_entity_registry_enabled_default = key in {
            "matching_assets",
            "frame_status",
        }

    @property
    @override
    def native_value(self) -> StateType:
        """Return the current metadata value."""
        if self.coordinator.data is None:
            return None
        return self._value(self.coordinator.data)
