"""The LoJack integration for Home Assistant."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from typing import Any

from lojack_api import ApiError, AuthenticationError, LoJackClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_UPDATE_INTERVAL, DOMAIN, LOGGER

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.DEVICE_TRACKER,
    Platform.SENSOR,
]

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
    license_plate: str | None
    odometer: float | None
    latitude: float | None
    longitude: float | None
    accuracy: float | None
    address: dict[str, Any] | str | None
    speed: float | None
    heading: float | None
    battery_voltage: float | None
    timestamp: datetime | str | None


@dataclass
class LoJackData:
    """Data class for LoJack runtime data."""

    client: LoJackClient
    coordinator: LoJackCoordinator
    devices: dict[str, Any]  # Device ID -> LoJack API device object


type LoJackConfigEntry = ConfigEntry[LoJackData]


def _safe_float(value: Any) -> float | None:
    """Safely convert a value to float."""
    if value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


async def async_setup_entry(hass: HomeAssistant, entry: LoJackConfigEntry) -> bool:
    """Set up LoJack from a config entry."""
    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]

    try:
        client = await LoJackClient.create(username, password)
    except AuthenticationError as err:
        raise ConfigEntryAuthFailed(f"Authentication failed: {err}") from err
    except ApiError as err:
        raise ConfigEntryNotReady(f"API error during setup: {err}") from err
    except Exception as err:
        LOGGER.error("Failed to authenticate with LoJack: %s", err)
        raise ConfigEntryNotReady(f"Connection failed: {err}") from err

    devices: dict[str, Any] = {}
    coordinator = LoJackCoordinator(hass, client, entry, devices)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = LoJackData(client=client, coordinator=coordinator, devices=devices)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: LoJackConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        try:
            await entry.runtime_data.client.close()
        except Exception:  # noqa: BLE001 - Cleanup during unload should not fail
            LOGGER.debug("Error closing LoJack client during unload")

    return unload_ok


class LoJackCoordinator(DataUpdateCoordinator[dict[str, LoJackVehicleData]]):
    """Class to manage fetching LoJack data."""

    config_entry: LoJackConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        client: LoJackClient,
        entry: LoJackConfigEntry,
        devices_dict: dict[str, Any],
    ) -> None:
        """Initialize the coordinator."""
        self.client = client
        self._username = entry.data[CONF_USERNAME]
        self._password = entry.data[CONF_PASSWORD]
        self._default_update_interval = timedelta(minutes=DEFAULT_UPDATE_INTERVAL)
        self._last_rate_limit: datetime | None = None
        self._devices = devices_dict  # Shared dict to store API device objects

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

        if headers and "Retry-After" in headers:
            val = headers.get("Retry-After")
            if val is None:
                return None
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
        self._last_rate_limit = datetime.now(tz=UTC)
        retry_after = self._extract_retry_after(err)

        if retry_after:
            new_interval = timedelta(seconds=retry_after)
            LOGGER.warning(
                "LoJack API rate limited: respecting Retry-After=%s seconds",
                retry_after,
            )
        else:
            new_interval = min(self.update_interval * 2, MAX_UPDATE_INTERVAL)
            LOGGER.warning(
                "LoJack API rate limited: increasing update interval to %s",
                new_interval,
            )

        # Enforce bounds
        new_interval = max(new_interval, MIN_UPDATE_INTERVAL)
        new_interval = min(new_interval, MAX_UPDATE_INTERVAL)

        self.update_interval = new_interval

    def _is_rate_limited(self, err: Exception) -> bool:
        """Check if an exception indicates rate limiting."""
        if getattr(err, "status", None) == 429:
            return True
        err_str = str(err)
        return "429" in err_str or "Too Many Requests" in err_str

    async def _async_update_data(self) -> dict[str, LoJackVehicleData]:
        """Fetch data from LoJack API."""
        try:
            devices = await self.client.list_devices()
        except AuthenticationError:
            LOGGER.info("Token expired, refreshing...")
            try:
                self.client = await LoJackClient.create(self._username, self._password)
                self.update_interval = self._default_update_interval
                devices = await self.client.list_devices()
            except Exception as refresh_err:
                raise ConfigEntryAuthFailed(
                    f"Failed to refresh token: {refresh_err}"
                ) from refresh_err
        except ApiError as err:
            if self._is_rate_limited(err):
                self._handle_rate_limit(err)
                raise UpdateFailed(f"Rate limited by LoJack API: {err}") from err
            raise UpdateFailed(f"Error fetching LoJack data: {err}") from err
        except Exception as err:
            if self._is_rate_limited(err):
                self._handle_rate_limit(err)
                raise UpdateFailed(f"Rate limited by LoJack API: {err}") from err
            raise UpdateFailed(f"Error fetching LoJack data: {err}") from err

        vehicles_data: dict[str, LoJackVehicleData] = {}

        # Clear and rebuild the devices dict
        self._devices.clear()

        for device in devices:
            device_id = getattr(device, "id", None)
            if not device_id:
                continue

            # Store the device object for direct access (e.g., by button entity)
            self._devices[str(device_id)] = device

            # Get latest location
            try:
                location = await device.get_location()
            except Exception:  # noqa: BLE001 - Location fetch can fail for many reasons
                location = None

            # Build vehicle data
            vehicle = LoJackVehicleData(
                device_id=str(device_id),
                name=getattr(device, "name", None),
                vin=getattr(device, "vin", None),
                make=getattr(device, "make", None),
                model=getattr(device, "model", None),
                year=str(getattr(device, "year", "") or ""),
                license_plate=getattr(device, "license_plate", None),
                odometer=_safe_float(getattr(device, "odometer", None)),
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
                speed=_safe_float(getattr(location, "speed", None))
                if location
                else None,
                heading=_safe_float(getattr(location, "heading", None))
                if location
                else None,
                battery_voltage=_safe_float(getattr(location, "battery_voltage", None))
                if location
                else None,
                timestamp=getattr(location, "timestamp", None) if location else None,
            )

            vehicles_data[str(device_id)] = vehicle

            LOGGER.debug(
                "Location data for device %s: lat=%s, lon=%s, accuracy=%s, speed=%s, "
                "battery_voltage=%s, timestamp=%s, heading=%s",
                device_id,
                vehicle.latitude,
                vehicle.longitude,
                vehicle.accuracy,
                vehicle.speed,
                vehicle.battery_voltage,
                vehicle.timestamp,
                vehicle.heading,
            )

        return vehicles_data
