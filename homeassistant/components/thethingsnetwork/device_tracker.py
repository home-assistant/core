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

    @property
    def entity_category(self) -> None:
        """Return None to prevent diagnostic categorization."""
        return None

    @property
    def latitude(self) -> float | None:
        """Return latitude from GPS if available."""
        coords = self._get_gps_coordinates()
        return coords[0] if coords else None

    @property
    def longitude(self) -> float | None:
        """Return longitude from GPS if available."""
        coords = self._get_gps_coordinates()
        return coords[1] if coords else None

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
        # Update if we have either Wi-Fi scan data or GPS coordinates
        if self._get_wifi_scan_data() or self._get_gps_coordinates():
            self.async_write_ha_state()

    def _get_gps_coordinates(self) -> tuple[float, float] | None:
        """Get GPS coordinates (latitude, longitude) if available."""
        device_uplinks = self.coordinator.data.get(self._device_id, {})

        lat = None
        lon = None

        for field_id, ttn_value in device_uplinks.items():
            if not isinstance(ttn_value, TTNSensorValue):
                continue

            if field_id == "Latitude_4198":
                lat = ttn_value.value
            elif field_id == "Longitude_4197":
                lon = ttn_value.value

        if lat is not None and lon is not None:
            return (float(lat), float(lon))
        return None

    def _get_wifi_scan_data(self) -> TTNSensorValue | None:
        """Get the latest Wi-Fi scan data for this device."""
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
        wifi_data = self._get_wifi_scan_data()
        if not wifi_data:
            return None

        # The value type can be list at runtime despite type hints
        value: Any = wifi_data.value
        if isinstance(value, list) and value:
            attrs: dict[str, Any] = {"wifi_access_points_count": len(value)}

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
                return attrs

        return None
