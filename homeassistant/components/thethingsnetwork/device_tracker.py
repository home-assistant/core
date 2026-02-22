"""The Things Network's integration device trackers."""

import logging
from typing import Any

from ttn_client import TTNSensorValue

from homeassistant.components.device_tracker import TrackerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_APP_ID, DOMAIN
from .coordinator import TTNCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add device trackers for TTN."""

    coordinator = hass.data[DOMAIN][entry.entry_id]

    # Track which devices have trackers (one per device, not per measurement)
    trackers: dict[str, TtnDeviceTracker] = {}

    def _async_measurement_listener() -> None:
        data = coordinator.data
        new_trackers = []

        for device_id, device_uplinks in data.items():
            # Check if this device has Wi-Fi scan data
            has_wifi_data = any(
                _is_location_data(ttn_value)
                for ttn_value in device_uplinks.values()
                if isinstance(ttn_value, TTNSensorValue)
            )

            if has_wifi_data and device_id not in trackers:
                # Create one tracker per device
                tracker = TtnDeviceTracker(
                    coordinator,
                    entry.data[CONF_APP_ID],
                    device_id,
                )
                trackers[device_id] = tracker
                new_trackers.append(tracker)

        if new_trackers:
            async_add_entities(new_trackers)

    entry.async_on_unload(coordinator.async_add_listener(_async_measurement_listener))
    _async_measurement_listener()


def _is_location_data(ttn_value: TTNSensorValue) -> bool:
    """Check if this is Wi-Fi scan, GPS, or other location-related data."""
    field_id = ttn_value.field_id

    # Check for GPS coordinates (Latitude or Longitude measurements)
    if field_id in ("Latitude_4198", "Longitude_4197"):
        return True

    # Check if the value is a list with mac addresses (Wi-Fi scan data)
    value: Any = ttn_value.value
    if isinstance(value, list) and value:
        # Wi-Fi scan data has dicts with 'mac' key
        if all(isinstance(item, dict) and "mac" in item for item in value):
            return True

    return False


class TtnDeviceTracker(CoordinatorEntity[TTNCoordinator], TrackerEntity):
    """Represents a TTN device tracker for location-based devices."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:map-marker-radius"

    def __init__(
        self,
        coordinator: TTNCoordinator,
        app_id: str,
        device_id: str,
    ) -> None:
        """Initialize a TTN device tracker."""
        super().__init__(coordinator)

        self._app_id = app_id
        self._device_id = device_id
        self._attr_unique_id = device_id
        self._attr_name = None  # Use device name

        # Store geocoded location (from external geolocation services)
        self._geocoded_lat: float | None = None
        self._geocoded_lon: float | None = None
        self._geocoded_accuracy: float | None = None

        # Track timestamps to handle out-of-order messages
        # (devices may buffer data when offline and send old data after new)
        self._last_wifi_timestamp: int | None = None
        self._last_gps_timestamp: int | None = None

        # Store the current location data (not just reference coordinator)
        self._current_wifi_data: TTNSensorValue | None = None
        self._current_gps_lat: float | None = None
        self._current_gps_lon: float | None = None

        # Populate initial data from coordinator
        self._initialize_from_coordinator()

    def _initialize_from_coordinator(self) -> None:
        """Populate initial data from coordinator during entity creation."""
        # Get initial Wi-Fi scan data
        wifi_data = self._get_new_wifi_scan_data()
        if wifi_data:
            self._current_wifi_data = wifi_data
            self._last_wifi_timestamp = self._get_measurement_timestamp(wifi_data)

        # Get initial GPS coordinates
        gps_data = self._get_new_gps_coordinates()
        if gps_data:
            self._current_gps_lat = gps_data[0]
            self._current_gps_lon = gps_data[1]
            self._last_gps_timestamp = gps_data[2]

    @property
    def entity_category(self) -> None:
        """Return None to prevent diagnostic categorization."""
        return None

    @property
    def latitude(self) -> float | None:
        """Return latitude from GPS or geocoded location."""
        # Prioritize GPS over geocoded location
        coords = self._get_gps_coordinates()
        if coords:
            return coords[0]
        # Fall back to geocoded location if no GPS
        return self._geocoded_lat

    @property
    def longitude(self) -> float | None:
        """Return longitude from GPS or geocoded location."""
        # Prioritize GPS over geocoded location
        coords = self._get_gps_coordinates()
        if coords:
            return coords[1]
        # Fall back to geocoded location if no GPS
        return self._geocoded_lon

    def set_geocoded_location(
        self, latitude: float, longitude: float, accuracy: float | None = None
    ) -> None:
        """Set geocoded location from external geolocation service."""
        self._geocoded_lat = latitude
        self._geocoded_lon = longitude
        self._geocoded_accuracy = accuracy
        self.async_write_ha_state()

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self._app_id}_{self._device_id}")},
            name=self._device_id,
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        updated = False

        # Check for new Wi-Fi scan data
        new_wifi = self._get_new_wifi_scan_data()
        if new_wifi:
            new_timestamp = self._get_measurement_timestamp(new_wifi)
            if self._is_newer_timestamp(new_timestamp, self._last_wifi_timestamp):
                self._current_wifi_data = new_wifi
                self._last_wifi_timestamp = new_timestamp
                updated = True

        # Check for new GPS coordinates
        new_gps = self._get_new_gps_coordinates()
        if new_gps:
            new_timestamp = new_gps[2]  # (lat, lon, timestamp)
            if self._is_newer_timestamp(new_timestamp, self._last_gps_timestamp):
                self._current_gps_lat = new_gps[0]
                self._current_gps_lon = new_gps[1]
                self._last_gps_timestamp = new_timestamp
                updated = True

        if updated:
            self.async_write_ha_state()

    def _get_measurement_timestamp(self, ttn_value: TTNSensorValue) -> int | None:
        """Extract measurement timestamp from TTNSensorValue."""
        if hasattr(ttn_value, "uplink") and isinstance(ttn_value.uplink, dict):
            return ttn_value.uplink.get("timestamp")
        return None

    def _is_newer_timestamp(
        self, new_timestamp: int | None, last_timestamp: int | None
    ) -> bool:
        """Check if new timestamp is newer than the last one."""
        # If we have no new timestamp, allow update (backwards compatibility)
        if new_timestamp is None:
            return True
        # If we have no previous timestamp, this is the first update
        if last_timestamp is None:
            return True
        # Only update if new timestamp is greater
        return new_timestamp > last_timestamp

    def _get_gps_coordinates(self) -> tuple[float, float] | None:
        """Get stored GPS coordinates (latitude, longitude) if available."""
        if self._current_gps_lat is not None and self._current_gps_lon is not None:
            return (self._current_gps_lat, self._current_gps_lon)
        return None

    def _get_new_gps_coordinates(self) -> tuple[float, float, int | None] | None:
        """Get new GPS coordinates from coordinator with timestamp."""
        device_uplinks = self.coordinator.data.get(self._device_id, {})

        lat = None
        lon = None
        timestamp = None

        for field_id, ttn_value in device_uplinks.items():
            if not isinstance(ttn_value, TTNSensorValue):
                continue

            if field_id == "Latitude_4198":
                lat = ttn_value.value
                # Get timestamp from this measurement
                if timestamp is None:
                    timestamp = self._get_measurement_timestamp(ttn_value)
            elif field_id == "Longitude_4197":
                lon = ttn_value.value
                # Get timestamp from this measurement if not already set
                if timestamp is None:
                    timestamp = self._get_measurement_timestamp(ttn_value)

        if lat is not None and lon is not None:
            return (float(lat), float(lon), timestamp)
        return None

    def _get_wifi_scan_data(self) -> TTNSensorValue | None:
        """Get stored Wi-Fi scan data for this device."""
        return self._current_wifi_data

    def _get_new_wifi_scan_data(self) -> TTNSensorValue | None:
        """Get new Wi-Fi scan data from coordinator."""
        device_uplinks = self.coordinator.data.get(self._device_id, {})
        for ttn_value in device_uplinks.values():
            if isinstance(ttn_value, TTNSensorValue) and _is_location_data(ttn_value):
                # Skip GPS measurements, only return Wi-Fi scan
                if ttn_value.field_id not in ("Latitude_4198", "Longitude_4197"):
                    return ttn_value
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra state attributes with Wi-Fi scan data for geolocation."""
        attrs: dict[str, Any] = {}

        # Add Wi-Fi scan data if available
        wifi_data = self._get_wifi_scan_data()
        if wifi_data:
            # The value type can be list at runtime despite type hints
            value: Any = wifi_data.value
            if isinstance(value, list) and value:
                attrs["wifi_access_points_count"] = len(value)

                # Wi-Fi scan data (list of dicts with mac/rssi)
                if all(isinstance(item, dict) and "mac" in item for item in value):
                    # Store Wi-Fi access points for geolocation services
                    wifi_aps = []
                    for idx, ap in enumerate(value, 1):
                        attrs[f"wifi_ap_{idx}_mac"] = ap.get("mac")
                        attrs[f"wifi_ap_{idx}_rssi"] = ap.get("rssi")
                        wifi_aps.append(
                            {
                                "macAddress": ap.get("mac"),
                                "signalStrength": int(ap.get("rssi", 0)),
                            }
                        )

                    # Store in format ready for Google Geolocation API
                    attrs["wifi_access_points"] = wifi_aps

            # Add Wi-Fi measurement timestamp
            if self._last_wifi_timestamp is not None:
                attrs["wifi_timestamp"] = self._last_wifi_timestamp

        # Add GPS timestamp if available
        if self._last_gps_timestamp is not None:
            attrs["gps_timestamp"] = self._last_gps_timestamp

        # Add geocoded location info if available
        if self._geocoded_lat is not None and self._geocoded_lon is not None:
            attrs["geocoded_latitude"] = self._geocoded_lat
            attrs["geocoded_longitude"] = self._geocoded_lon
            if self._geocoded_accuracy is not None:
                attrs["geocoded_accuracy"] = self._geocoded_accuracy

            # Indicate if we're currently showing geocoded location
            if not self._get_gps_coordinates():
                attrs["location_source"] = "geocoded"
            else:
                attrs["location_source"] = "gps"

        return attrs if attrs else None
