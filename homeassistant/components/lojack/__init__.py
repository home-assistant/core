"""The LoJack integration for Home Assistant."""
from __future__ import annotations

import logging
from datetime import timedelta, datetime
from typing import TYPE_CHECKING, Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from lojack_api import LoJackClient, AuthenticationError, ApiError

from .const import (
    DATA_ASSETS,
    DATA_CLIENT,
    DATA_COORDINATOR,
    DEFAULT_POLL_INTERVAL,
    MIN_POLL_INTERVAL,
    MAX_POLL_INTERVAL,
    DOMAIN,
)

if TYPE_CHECKING:
    from lojack_api import LoJackClient

_LOGGER = logging.getLogger(__name__)

PLATFORMS_LIST: list[Platform] = [Platform.DEVICE_TRACKER, Platform.SENSOR, Platform.BINARY_SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up LoJack from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]

    try:
        client = await _authenticate(hass, username, password)
    except AuthenticationError as err:
        raise ConfigEntryAuthFailed(f"Authentication failed: {err}") from err
    except ApiError as err:
        raise ConfigEntryAuthFailed(f"API error: {err}") from err
    except Exception as err:
        _LOGGER.error("Failed to authenticate with LoJack: %s", err)
        raise ConfigEntryAuthFailed(f"Authentication failed: {err}") from err

    # Create the data update coordinator
    coordinator = LoJackDataUpdateCoordinator(hass, client, entry)

    # Fetch initial data
    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = {
        DATA_CLIENT: client,
        DATA_COORDINATOR: coordinator,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS_LIST)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS_LIST)

    if unload_ok:
        data = hass.data[DOMAIN].pop(entry.entry_id)
        client: LoJackClient = data[DATA_CLIENT]
        await client.close()

    return unload_ok


async def _authenticate(hass: HomeAssistant, username: str, password: str) -> "LoJackClient":
    """Authenticate with LoJack and return an async LoJackClient."""
    from lojack_api import LoJackClient

    # v0.5.0 API: create(username, password)
    client = await LoJackClient.create(username, password)
    return client


async def _refresh_token(hass: HomeAssistant, username: str, password: str) -> "LoJackClient":
    """Refresh the authentication by creating a new client."""
    return await _authenticate(hass, username, password)


class LoJackDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Class to manage fetching LoJack data."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: "LoJackClient",
        entry: ConfigEntry,
    ) -> None:
        """Initialize the coordinator."""
        self.client = client
        self.entry = entry
        self._username = entry.data[CONF_USERNAME]
        self._password = entry.data[CONF_PASSWORD]

        # Configure default update interval from entry options
        default_minutes = entry.options.get("poll_interval", DEFAULT_POLL_INTERVAL)
        self._default_update_interval = timedelta(minutes=default_minutes)
        self._min_update_interval = timedelta(minutes=MIN_POLL_INTERVAL)
        self._max_update_interval = timedelta(minutes=MAX_POLL_INTERVAL)

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=self._default_update_interval,
        )

        # track when we last hit rate limits to avoid rapid flips
        self._last_rate_limit: datetime | None = None

    def _extract_retry_after(self, err: Exception) -> int | None:
        """Try to extract Retry-After seconds from an exception or its response headers."""
        # Lazy import for parsing
        from email.utils import parsedate_to_datetime

        # Common places headers might be stored on wrapped exceptions
        headers = getattr(err, "headers", None)
        if not headers:
            resp = getattr(err, "response", None)
            if resp is not None:
                headers = getattr(resp, "headers", None)

        if headers and "Retry-After" in headers:
            val = headers.get("Retry-After")
            if val is None:
                return None
            # Retry-After may be seconds or HTTP-date
            try:
                return int(val)
            except Exception:
                try:
                    retry_dt = parsedate_to_datetime(val)
                    # parsedate_to_datetime returns aware datetime when possible
                    now = datetime.utcnow()
                    if retry_dt.tzinfo is not None:
                        retry_dt = retry_dt.astimezone(tz=None).replace(tzinfo=None)
                    secs = int((retry_dt - now).total_seconds())
                    return max(0, secs)
                except Exception:
                    return None


    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from LoJack API."""
        try:
            devices = await self.client.list_devices()

            assets_data: dict[str, Any] = {}

            for device in devices:
                device_id = getattr(device, "id", None)
                if not device_id:
                    continue

                # Try to get latest location
                try:
                    location = await device.get_location()
                except Exception:
                    location = None

                asset: dict[str, Any] = {
                    "id": device_id,
                    "name": getattr(device, "name", None),
                    "vin": getattr(device, "vin", None),
                    "make": getattr(device, "make", None),
                    "model": getattr(device, "model", None),
                    "year": getattr(device, "year", None),
                    "licensePlate": getattr(device, "license_plate", None),
                    "odometer": getattr(device, "odometer", None),
                }

                if location:
                    coords = None
                    if getattr(location, "latitude", None) is not None and getattr(location, "longitude", None) is not None:
                        coords = {
                            "latitude": getattr(location, "latitude", None),
                            "longitude": getattr(location, "longitude", None),
                        }

                    # Get raw location data for debugging
                    raw_data = getattr(location, "raw", None)
                    accuracy_val = getattr(location, "accuracy", None)
                    speed_val = getattr(location, "speed", None)
                    battery_voltage_val = getattr(location, "battery_voltage", None)
                    timestamp_val = getattr(location, "timestamp", None)

                    # Log all location attributes for debugging data freshness and accuracy
                    _LOGGER.debug(
                        "Location data for device %s: lat=%s, lon=%s, accuracy=%s, speed=%s, "
                        "battery_voltage=%s, timestamp=%s, heading=%s",
                        device_id,
                        getattr(location, "latitude", None),
                        getattr(location, "longitude", None),
                        accuracy_val,
                        speed_val,
                        battery_voltage_val,
                        timestamp_val,
                        getattr(location, "heading", None),
                    )
                    # Log raw data separately at a more verbose level to help debug accuracy/staleness issues
                    if raw_data:
                        _LOGGER.debug(
                            "Raw location data for device %s: %s",
                            device_id,
                            raw_data,
                        )

                    asset_location: dict[str, Any] = {
                        "coordinates": coords,
                        "accuracy": accuracy_val,
                        "address": getattr(location, "address", None),
                        "timestamp": timestamp_val,
                        "speed": speed_val,
                        "heading": getattr(location, "heading", None),
                        "battery_voltage": battery_voltage_val,
                        "raw": raw_data,
                    }

                    asset["location"] = asset_location

                assets_data[str(device_id)] = asset

            return {DATA_ASSETS: assets_data}
        except AuthenticationError as err:
            _LOGGER.info("Token expired, refreshing...")
            try:
                self.client = await _refresh_token(self.hass, self._username, self._password)
                # After reauth, restore default polling interval
                self.update_interval = self._default_update_interval
                return await self._async_update_data()
            except Exception as refresh_err:
                raise ConfigEntryAuthFailed(
                    f"Failed to refresh token: {refresh_err}"
                ) from refresh_err

        except ApiError as err:
            # Detect rate limit responses (429) and adapt polling interval
            retry_after = self._extract_retry_after(err)
            is_rate_limited = False
            if getattr(err, "status", None) == 429 or "429" in str(err) or "Too Many Requests" in str(err):
                is_rate_limited = True

            if is_rate_limited:
                self._last_rate_limit = datetime.utcnow()
                if retry_after:
                    new_interval = timedelta(seconds=retry_after)
                    _LOGGER.warning(
                        "LoJack API rate limited: respecting Retry-After=%s seconds; setting update interval to %s",
                        retry_after,
                        new_interval,
                    )
                else:
                    # Exponential backoff (double up to max)
                    new_interval = min(self.update_interval * 2, self._max_update_interval)
                    _LOGGER.warning(
                        "LoJack API rate limited: increasing update interval to %s",
                        new_interval,
                    )

                # Enforce reasonable bounds
                if new_interval < self._min_update_interval:
                    new_interval = self._min_update_interval
                if new_interval > self._max_update_interval:
                    new_interval = self._max_update_interval

                self.update_interval = new_interval
                raise UpdateFailed(f"Rate limited by LoJack API: {err}") from err

            # Non-rate-limit API errors are treated as update failures
            raise UpdateFailed(f"Error fetching LoJack data: {err}") from err

        except Exception as err:
            # Also detect generic rate-limit indications in unexpected exceptions
            retry_after = self._extract_retry_after(err)
            if getattr(err, "status", None) == 429 or "429" in str(err) or "Too Many Requests" in str(err) or retry_after:
                self._last_rate_limit = datetime.utcnow()
                if retry_after:
                    new_interval = timedelta(seconds=retry_after)
                    _LOGGER.warning(
                        "LoJack API rate limited (generic exception): respecting Retry-After=%s seconds; setting update interval to %s",
                        retry_after,
                        new_interval,
                    )
                else:
                    new_interval = min(self.update_interval * 2, self._max_update_interval)
                    _LOGGER.warning(
                        "LoJack API rate limited (generic exception): increasing update interval to %s",
                        new_interval,
                    )

                if new_interval < self._min_update_interval:
                    new_interval = self._min_update_interval
                if new_interval > self._max_update_interval:
                    new_interval = self._max_update_interval

                self.update_interval = new_interval
                raise UpdateFailed(f"Rate limited by LoJack API: {err}") from err

            if "401" in str(err) or "unauthorized" in str(err).lower():
                _LOGGER.info("Token expired, refreshing...")
                try:
                    self.client = await _refresh_token(self.hass, self._username, self._password)
                    # After successful refresh, restore default polling interval
                    self.update_interval = self._default_update_interval
                    return await self._async_update_data()
                except Exception as refresh_err:
                    raise ConfigEntryAuthFailed(
                        f"Failed to refresh token: {refresh_err}"
                    ) from refresh_err

            raise UpdateFailed(f"Error fetching LoJack data: {err}") from err
