"""Demo platform that has a couple of fake device trackers."""

from homeassistant.components.device_tracker import (
    BaseScannerEntity,
    SourceType,
    TrackerEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Everything but the Kitchen Sink config entry."""
    async_add_entities(
        [
            DemoTracker(
                unique_id="kitchen_sink_tracker_001",
                name="Demo tracker",
                latitude=hass.config.latitude,
                longitude=hass.config.longitude,
                accuracy=10,
            ),
            DemoScanner(
                unique_id="kitchen_sink_scanner_001",
                name="Demo scanner",
                is_connected=True,
            ),
        ]
    )


class DemoTracker(TrackerEntity):
    """Representation of a demo tracker."""

    _attr_should_poll = False
    _attr_source_type = SourceType.GPS

    def __init__(
        self,
        *,
        unique_id: str,
        name: str,
        latitude: float | None,
        longitude: float | None,
        accuracy: float,
    ) -> None:
        """Initialize the tracker."""
        self._attr_unique_id = unique_id
        self._attr_name = name
        self._attr_latitude = latitude
        self._attr_longitude = longitude
        self._attr_location_accuracy = accuracy

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

    _attr_should_poll = False
    _attr_source_type = SourceType.ROUTER

    def __init__(
        self,
        *,
        unique_id: str,
        name: str,
        is_connected: bool,
    ) -> None:
        """Initialize the scanner."""
        self._attr_unique_id = unique_id
        self._attr_name = name
        self._is_connected = is_connected

    @property
    def is_connected(self) -> bool:
        """Return true if the device is connected."""
        return self._is_connected

    @callback
    def async_set_scanner_connected(self, connected: bool) -> None:
        """Update the scanner connected state."""
        self._is_connected = connected
        self.async_write_ha_state()
