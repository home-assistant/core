"""Data update coordinator for the LoJack integration."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from typing import TYPE_CHECKING, Any

from lojack_api import ApiError, AuthenticationError, LoJackClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_UPDATE_INTERVAL, DOMAIN, LOGGER

if TYPE_CHECKING:
    from . import LoJackConfigEntry

# Rate limit bounds
MIN_UPDATE_INTERVAL = timedelta(minutes=1)
MAX_UPDATE_INTERVAL = timedelta(minutes=60)


@dataclass
class LoJackVehicleData:
    """Data class for vehicle data."""

    device_id: str
    name: str | None
    vin: str | None
    make: str | None
    model: str | None
    year: str | None
    latitude: float | None
    longitude: float | None
    accuracy: float | None
    address: dict[str, Any] | str | None
    heading: float | None
    timestamp: datetime | str | None


def get_device_name(vehicle: LoJackVehicleData) -> str:
    """Get a human-readable name for a vehicle."""
    if vehicle.year and vehicle.make and vehicle.model:
        return f"{vehicle.year} {vehicle.make} {vehicle.model}"
    if vehicle.make and vehicle.model:
        return f"{vehicle.make} {vehicle.model}"
    if vehicle.name:
        return vehicle.name
    return "Vehicle"


def _safe_float(value: Any) -> float | None:
    """Safely convert a value to float."""
    if value is None:
        return None
    # Explicitly reject booleans (bool is subclass of int, so bool would convert)
    if isinstance(value, bool):
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


class LoJackCoordinator(DataUpdateCoordinator[dict[str, LoJackVehicleData]]):
    """Class to manage fetching LoJack data."""

    config_entry: LoJackConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        client: LoJackClient,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the coordinator."""
        self.client = client
        self._username = entry.data[CONF_USERNAME]
        self._password = entry.data[CONF_PASSWORD]
        self._default_update_interval = timedelta(minutes=DEFAULT_UPDATE_INTERVAL)

        super().__init__(
            hass,
            LOGGER,
            name=DOMAIN,
            update_interval=self._default_update_interval,
            config_entry=entry,
        )

    def _extract_retry_after(self, err: Exception) -> int | None:
        """Extract Retry-After seconds from an exception or its response headers."""
        headers = getattr(err, "headers", None)
        if not headers:
            resp = getattr(err, "response", None)
            if resp is not None:
                headers = getattr(resp, "headers", None)

        val = None
        if headers:
            # HTTP header names are case-insensitive; perform a
            # case-insensitive lookup for maximum compatibility.
            for key in headers:
                if isinstance(key, str) and key.lower() == "retry-after":
                    val = headers.get(key)
                    break

        if val is not None:
            try:
                return int(val)
            except (ValueError, TypeError):
                try:
                    retry_dt = parsedate_to_datetime(val)
                    now = datetime.now(tz=UTC)
                    # Make sure retry_dt is timezone-aware for comparison
                    if retry_dt.tzinfo is None:
                        retry_dt = retry_dt.replace(tzinfo=UTC)
                    secs = int((retry_dt - now).total_seconds())
                    return max(0, secs)
                except (ValueError, TypeError):
                    return None
        return None

    def _handle_rate_limit(self, err: Exception) -> None:
        """Handle rate limiting by adjusting update interval."""
        retry_after = self._extract_retry_after(err)

        if retry_after is not None:
            new_interval = timedelta(seconds=retry_after)
        else:
            current_interval = self.update_interval or self._default_update_interval
            new_interval = current_interval * 2

        # Enforce bounds before logging so the logged value reflects what's used
        new_interval = max(new_interval, MIN_UPDATE_INTERVAL)
        new_interval = min(new_interval, MAX_UPDATE_INTERVAL)

        LOGGER.warning(
            "API rate limited: next update in %s",
            new_interval,
        )

        self.update_interval = new_interval

    def _is_rate_limited(self, err: Exception) -> bool:
        """Check if an exception indicates rate limiting."""
        if getattr(err, "status", None) == 429:
            return True
        err_str = str(err)
        return "429" in err_str or "Too Many Requests" in err_str

    async def _async_update_data(self) -> dict[str, LoJackVehicleData]:
        """Fetch data from API."""
        try:
            devices = await self.client.list_devices() or []
        except AuthenticationError:
            LOGGER.debug("Token expired, refreshing")
            old_client = self.client
            try:
                new_client = await LoJackClient.create(self._username, self._password)
                self.client = new_client
                self.update_interval = self._default_update_interval
                devices = await self.client.list_devices() or []
            except AuthenticationError as refresh_err:
                raise ConfigEntryAuthFailed(
                    f"Failed to refresh token: {refresh_err}"
                ) from refresh_err
            except Exception as refresh_err:
                raise UpdateFailed(
                    f"Error fetching data after token refresh: {refresh_err}"
                ) from refresh_err
            finally:
                try:
                    await old_client.close()
                except Exception:  # noqa: BLE001 - Best-effort cleanup
                    LOGGER.debug("Error closing previous client during token refresh", exc_info=True)
        except ApiError as err:
            if self._is_rate_limited(err):
                self._handle_rate_limit(err)
                raise UpdateFailed(f"Rate limited by API: {err}") from err
            raise UpdateFailed(f"Error fetching data: {err}") from err
        except Exception as err:
            if self._is_rate_limited(err):
                self._handle_rate_limit(err)
                raise UpdateFailed(f"Rate limited by API: {err}") from err
            raise UpdateFailed(f"Error fetching data: {err}") from err

        # Fetch all vehicle locations concurrently to reduce latency and
        # lower the chance of hitting per-request rate limits.
        results = await asyncio.gather(
            *[self._fetch_vehicle_data(device) for device in devices],
        )

        # Reset update interval after a successful fetch in case it was backed
        # off due to rate limiting (the token-refresh path resets it separately).
        if self.update_interval != self._default_update_interval:
            LOGGER.info(
                "Rate limit cleared, resuming normal update interval (%s)",
                self._default_update_interval,
            )
            self.update_interval = self._default_update_interval

        return {
            vehicle.device_id: vehicle
            for vehicle in results
            if vehicle is not None
        }

    async def _fetch_vehicle_data(self, device: Any) -> LoJackVehicleData | None:
        """Fetch data for a single vehicle device."""
        device_id = getattr(device, "id", None)
        if not device_id:
            return None

        try:
            location = await device.get_location()
        except Exception:  # noqa: BLE001 - Location fetch can fail for many reasons
            location = None

        vehicle = LoJackVehicleData(
            device_id=str(device_id),
            name=getattr(device, "name", None),
            vin=getattr(device, "vin", None),
            make=getattr(device, "make", None),
            model=getattr(device, "model", None),
            year=getattr(device, "year", None) or None,
            latitude=_safe_float(getattr(location, "latitude", None))
            if location
            else None,
            longitude=_safe_float(getattr(location, "longitude", None))
            if location
            else None,
            accuracy=_safe_float(getattr(location, "accuracy", None))
            if location
            else None,
            address=getattr(location, "address", None) if location else None,
            heading=_safe_float(getattr(location, "heading", None))
            if location
            else None,
            timestamp=getattr(location, "timestamp", None) if location else None,
        )

        LOGGER.debug(
            "Location data for device %s: present=%s, has_accuracy=%s, "
            "has_heading=%s, timestamp=%s",
            device_id,
            vehicle.latitude is not None and vehicle.longitude is not None,
            vehicle.accuracy is not None,
            vehicle.heading is not None,
            vehicle.timestamp,
        )

        return vehicle
