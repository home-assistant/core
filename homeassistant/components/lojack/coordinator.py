"""Data update coordinator for LoJack."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from lojack_api import ApiError, AuthenticationError, LoJackClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_UPDATE_INTERVAL, DOMAIN, LOGGER


@dataclass
class LoJackVehicleData:
    """Data class for LoJack vehicle information."""

    device_id: str
    name: str | None
    vin: str | None
    make: str | None
    model: str | None
    year: str | None
    color: str | None
    license_plate: str | None
    odometer: float | None
    latitude: float | None
    longitude: float | None
    accuracy: float | None
    address: str | None
    speed: float | None
    heading: float | None
    battery_voltage: float | None
    engine_hours: float | None
    timestamp: str | None


@dataclass
class LoJackData:
    """Data class for LoJack runtime data."""

    client: LoJackClient
    coordinators: dict[str, LoJackCoordinator]


type LoJackConfigEntry = ConfigEntry[LoJackData]


class LoJackCoordinator(DataUpdateCoordinator[LoJackVehicleData]):
    """Coordinator for fetching LoJack vehicle data."""

    config_entry: LoJackConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: LoJackConfigEntry,
        client: LoJackClient,
        device_id: str,
        initial_data: dict[str, Any],
    ) -> None:
        """Initialize the coordinator."""
        self.client = client
        self.device_id = device_id
        self._initial_data = initial_data
        self._username = entry.data[CONF_USERNAME]
        self._password = entry.data[CONF_PASSWORD]

        super().__init__(
            hass,
            LOGGER,
            name=f"{DOMAIN}_{device_id}",
            config_entry=entry,
            update_interval=timedelta(minutes=DEFAULT_UPDATE_INTERVAL),
        )

    def _parse_vehicle_data(self, device: Any) -> LoJackVehicleData:
        """Parse device data into LoJackVehicleData."""
        location = getattr(device, "location", None) or {}
        if isinstance(location, dict):
            coords = location.get("coordinates", {})
            lat = coords.get("latitude") if coords else location.get("latitude")
            lon = coords.get("longitude") if coords else location.get("longitude")
        else:
            coords = getattr(location, "coordinates", None)
            if coords:
                lat = getattr(coords, "latitude", None)
                lon = getattr(coords, "longitude", None)
            else:
                lat = getattr(location, "latitude", None)
                lon = getattr(location, "longitude", None)

        def safe_get(obj: Any, attr: str, default: Any = None) -> Any:
            """Safely get attribute from object or dict."""
            if obj is None:
                return default
            if isinstance(obj, dict):
                return obj.get(attr, default)
            return getattr(obj, attr, default)

        return LoJackVehicleData(
            device_id=self.device_id,
            name=safe_get(device, "name"),
            vin=safe_get(device, "vin"),
            make=safe_get(device, "make"),
            model=safe_get(device, "model"),
            year=str(safe_get(device, "year", "")) or None,
            color=safe_get(device, "color"),
            license_plate=safe_get(device, "license_plate"),
            odometer=safe_get(device, "odometer"),
            latitude=float(lat) if lat is not None else None,
            longitude=float(lon) if lon is not None else None,
            accuracy=safe_get(location, "accuracy"),
            address=self._format_address(safe_get(location, "address")),
            speed=safe_get(location, "speed"),
            heading=safe_get(location, "heading"),
            battery_voltage=safe_get(location, "battery_voltage"),
            engine_hours=safe_get(location, "engine_hours"),
            timestamp=safe_get(location, "timestamp"),
        )

    def _format_address(self, addr: Any) -> str | None:
        """Format address from API response."""
        if addr is None:
            return None
        if isinstance(addr, str):
            return addr
        if isinstance(addr, dict):
            parts: list[str] = []
            for key in ("line1", "line2", "city", "stateOrProvince", "postalCode"):
                val = addr.get(key)
                if val:
                    parts.append(str(val))
            return ", ".join(parts) if parts else str(addr)
        return str(addr)

    async def _async_update_data(self) -> LoJackVehicleData:
        """Fetch data from LoJack API."""
        try:
            devices = await self.client.list_devices()

            for device in devices:
                device_id = getattr(device, "id", None)
                if str(device_id) != self.device_id:
                    continue

                # Get location data
                try:
                    location = await device.get_location()
                    device.location = {
                        "coordinates": {
                            "latitude": getattr(location, "latitude", None),
                            "longitude": getattr(location, "longitude", None),
                        },
                        "accuracy": getattr(location, "accuracy", None),
                        "address": getattr(location, "address", None),
                        "speed": getattr(location, "speed", None),
                        "heading": getattr(location, "heading", None),
                        "battery_voltage": getattr(location, "battery_voltage", None),
                        "engine_hours": getattr(location, "engine_hours", None),
                        "timestamp": getattr(location, "timestamp", None),
                    }
                except Exception:  # noqa: BLE001
                    LOGGER.debug("Could not get location for device %s", self.device_id)
                    device.location = {}

                return self._parse_vehicle_data(device)

            # Device not found, use initial data
            LOGGER.warning("Device %s not found in API response", self.device_id)
            raise UpdateFailed(f"Device {self.device_id} not found")

        except AuthenticationError:
            LOGGER.debug("Authentication failed, attempting re-auth")
            try:
                self.client = await LoJackClient.create(self._username, self._password)
                # Update client reference in runtime data
                if self.config_entry.runtime_data:
                    self.config_entry.runtime_data.client = self.client
                    for coord in self.config_entry.runtime_data.coordinators.values():
                        coord.client = self.client
                return await self._async_update_data()
            except AuthenticationError as reauth_err:
                raise ConfigEntryAuthFailed(
                    "Authentication failed after re-auth attempt"
                ) from reauth_err

        except ApiError as err:
            # Check for rate limiting
            status = getattr(err, "status", None)
            if status == 429 or "429" in str(err) or "Too Many Requests" in str(err):
                LOGGER.warning("LoJack API rate limited")
            raise UpdateFailed(f"Error communicating with LoJack API: {err}") from err
