"""Demo platform that has a couple of fake device trackers."""

from dataclasses import dataclass
from typing import override

from homeassistant.components.device_tracker import (
    BaseScannerEntity,
    ScannerEntityDescription,
    SourceType,
    TrackerEntity,
    TrackerEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback


@dataclass(frozen=True, kw_only=True)
class DemoTrackerEntityDescription(TrackerEntityDescription):
    """Describes a demo tracker."""

    accuracy: float


@dataclass(frozen=True, kw_only=True)
class DemoScannerEntityDescription(ScannerEntityDescription):
    """Describes a demo scanner."""

    is_connected: bool


TRACKERS = (
    DemoTrackerEntityDescription(
        key="kitchen_sink_tracker_001", name="Demo tracker", accuracy=10
    ),
)

SCANNERS = (
    DemoScannerEntityDescription(
        key="kitchen_sink_scanner_001", name="Demo scanner", is_connected=True
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Everything but the Kitchen Sink config entry."""
    async_add_entities(
        [
            *(
                DemoTracker(
                    description,
                    latitude=hass.config.latitude,
                    longitude=hass.config.longitude,
                )
                for description in TRACKERS
            ),
            *(DemoScanner(description) for description in SCANNERS),
        ]
    )


class DemoTracker(TrackerEntity):
    """Representation of a demo tracker."""

    entity_description: DemoTrackerEntityDescription
    _attr_should_poll = False
    _attr_source_type = SourceType.GPS

    def __init__(
        self,
        description: DemoTrackerEntityDescription,
        *,
        latitude: float | None,
        longitude: float | None,
    ) -> None:
        """Initialize the tracker."""
        self.entity_description = description
        self._attr_unique_id = description.key
        self._attr_latitude = latitude
        self._attr_longitude = longitude
        self._attr_location_accuracy = description.accuracy

    @callback
    def async_set_tracker_location(
        self, latitude: float, longitude: float, accuracy: float
    ) -> None:
        """Update the tracker location."""
        self._attr_latitude = latitude
        self._attr_longitude = longitude
        self._attr_location_accuracy = accuracy
        self.async_write_ha_state()


class DemoScanner(BaseScannerEntity):
    """Representation of a demo scanner."""

    entity_description: DemoScannerEntityDescription
    _attr_should_poll = False
    _attr_source_type = SourceType.ROUTER

    def __init__(self, description: DemoScannerEntityDescription) -> None:
        """Initialize the scanner."""
        self.entity_description = description
        self._attr_unique_id = description.key
        self._is_connected = description.is_connected

    @property
    @override
    def is_connected(self) -> bool:
        """Return true if the device is connected."""
        return self._is_connected

    @callback
    def async_set_scanner_connected(self, connected: bool) -> None:
        """Update the scanner connected state."""
        self._is_connected = connected
        self.async_write_ha_state()
