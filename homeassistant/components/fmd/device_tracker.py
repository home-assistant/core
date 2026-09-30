"""Device tracker for FMD integration."""

import asyncio
from collections.abc import Callable
from datetime import datetime, timedelta
import json
import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from fmd_api import FmdClient  # pragma: no cover

from fmd_api import AuthenticationError, FmdApiException, OperationError

from homeassistant.components.device_tracker import SourceType, TrackerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util import dt as dt_util

from .const import (
    CONF_USE_IMPERIAL,
    DEFAULT_HIGH_FREQUENCY_INTERVAL,
    DEFAULT_POLLING_INTERVAL,
    DOMAIN,
    METERS_TO_FEET,
    MPS_TO_MPH,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the FMD device tracker.

    Raises ConfigEntryNotReady if the initial location fetch fails,
    allowing Home Assistant to retry with exponential backoff.
    """
    _LOGGER.info("Setting up FMD device tracker for %s", entry.data["id"])

    # Get the API instance created in __init__.py
    api = entry.runtime_data.api

    # Get polling interval (preferring the number entity value, falling back to legacy config)
    polling_interval = entry.data.get(
        "update_interval_native_value",
        entry.data.get("polling_interval", DEFAULT_POLLING_INTERVAL),
    )

    # Get high frequency interval
    high_frequency_interval = entry.data.get(
        "high_frequency_interval_native_value", DEFAULT_HIGH_FREQUENCY_INTERVAL
    )

    # Get allow_inaccurate setting, defaulting to False (blocking enabled)
    # For backward compatibility, also check old "block_inaccurate" key
    allow_inaccurate = bool(
        entry.data.get(
            "allow_inaccurate_locations", not entry.data.get("block_inaccurate", True)
        )
    )
    block_inaccurate = not allow_inaccurate  # Internal logic still uses block

    # Get imperial units setting, defaulting to False (use metric)
    use_imperial = bool(entry.data.get(CONF_USE_IMPERIAL, False))

    tracker = FmdDeviceTracker(
        hass,
        entry,
        api,
        int(polling_interval),
        int(high_frequency_interval),
        block_inaccurate,
        use_imperial,
    )

    # Store tracker in runtime data for access by other entities
    entry.runtime_data.tracker = tracker

    # Fetch initial location before adding the entity
    # Note: We don't raise ConfigEntryNotReady here because this is platform-level setup.
    # Platform failures should be handled gracefully - the tracker will be added with
    # "unknown" state and will retry during normal polling.
    _LOGGER.info("Fetching initial location data...")
    try:
        await tracker.async_update()
        _LOGGER.info(
            "Initial location: lat=%s, lon=%s", tracker.latitude, tracker.longitude
        )
    except Exception as err:  # noqa: BLE001
        _LOGGER.warning(
            "Failed to fetch initial location (will retry during polling): %s", err
        )

    async_add_entities([tracker])
    _LOGGER.info("FMD device tracker added")

    # Start the polling timer
    tracker.start_polling()


class FmdDeviceTracker(TrackerEntity):
    """Represent a tracked device."""

    _attr_has_entity_name = True
    _attr_entity_category = (
        None  # Explicitly set to None to ensure it's a primary entity
    )

    _location: dict[str, Any] | None
    _battery_level: int | None
    _last_poll_time: str | None
    _remove_timer: Callable[[], None] | None
    _is_updating: bool

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        api: FmdClient,
        polling_interval: int,
        high_frequency_interval: int,
        block_inaccurate: bool,
        use_imperial: bool,
    ):
        """Initialize the device tracker."""
        self.hass = hass
        self._entry = entry
        self.api = api
        self._normal_interval = polling_interval  # Normal polling interval
        self._polling_interval = polling_interval  # Current active interval
        self._high_frequency_interval = high_frequency_interval  # High-freq interval
        self._high_frequency_mode = False  # Whether high-freq mode is active
        self._block_inaccurate = block_inaccurate
        self._use_imperial = use_imperial  # Whether to convert units to imperial
        self._location = None
        # Primary device entity: with has_entity_name the entity takes the
        # device's name ("FMD <id>"); entity_id stays device_tracker.fmd_<id>.
        self._attr_name = None
        self._battery_level = None
        self._last_poll_time = None  # When we last polled FMD server
        self._remove_timer = None
        self._is_updating = False

    @property
    def block_inaccurate(self) -> bool:
        """Return whether inaccurate location filtering is enabled."""
        return self._block_inaccurate

    @block_inaccurate.setter
    def block_inaccurate(self, value: bool) -> None:
        """Set inaccurate location filtering."""
        self._block_inaccurate = value

    @property
    def polling_interval(self) -> int:
        """Return the polling interval."""
        return self._polling_interval

    def start_polling(self) -> None:
        """Start the polling timer."""
        if self._remove_timer:
            self._remove_timer()

        async def update_locations(now: datetime | None = None) -> None:
            """Update device locations."""
            # Prevent overlapping updates if the previous one is still running
            if self._is_updating:
                _LOGGER.warning("Previous update still in progress, skipping this poll")
                return

            self._is_updating = True
            try:
                # If in high-frequency mode, request fresh location from device
                if self._high_frequency_mode:
                    _LOGGER.debug(
                        "High-frequency mode active - requesting fresh location from device"
                    )
                    try:
                        # Determine provider based on "Location Source" select entity
                        # Default to "all" if entity not found or state unknown
                        provider = "all"
                        location_source_entity_id = (
                            f"select.fmd_{self._entry.data['id']}_location_source"
                        )
                        location_source_state = self.hass.states.get(
                            location_source_entity_id
                        )

                        if location_source_state:
                            selected_option = location_source_state.state
                            provider_map: dict[str, str] = {
                                "All Providers (Default)": "all",
                                "GPS Only (Accurate)": "gps",
                                "Cell Only (Fast)": "cell",
                                "Last Known (No Request)": "last",
                            }
                            provider = provider_map.get(selected_option, "all")
                            _LOGGER.debug(
                                "Using location source: %s (provider=%s)",
                                selected_option,
                                provider,
                            )

                        # Request location with the selected provider
                        success = await self.api.request_location(provider=provider)
                        if success:
                            _LOGGER.debug(
                                "Location request sent, waiting 10 seconds for device..."
                            )
                            # Wait for device to process command and upload location
                            await asyncio.sleep(10)
                        else:
                            _LOGGER.warning("Failed to request location from device")
                    except Exception as e:  # noqa: BLE001
                        _LOGGER.error(
                            "Error requesting location during high-frequency poll: %s",
                            e,
                        )

                # Fetch location from server and update state
                await self.async_update()
                self.async_write_ha_state()
            finally:
                self._is_updating = False

        _LOGGER.info(
            "Starting polling with interval: %s minutes", self._polling_interval
        )
        self._remove_timer = async_track_time_interval(
            self.hass, update_locations, timedelta(minutes=self._polling_interval)
        )

    def set_polling_interval(self, interval_minutes: int) -> None:
        """Update the polling interval and restart the timer."""
        _LOGGER.info(
            "Updating polling interval from %s to %s minutes",
            self._polling_interval,
            interval_minutes,
        )
        self._polling_interval = interval_minutes
        # If not in high-frequency mode, also update the stored normal interval
        if not self._high_frequency_mode:
            self._normal_interval = interval_minutes
        self.start_polling()

    def set_high_frequency_interval(self, interval_minutes: int) -> None:
        """Update the high-frequency interval value."""
        _LOGGER.info("Setting high-frequency interval to %s minutes", interval_minutes)
        self._high_frequency_interval = interval_minutes
        # If already in high-frequency mode, apply the new interval immediately
        if self._high_frequency_mode:
            _LOGGER.info(
                "High-frequency mode is active, applying new interval immediately"
            )
            self.set_polling_interval(interval_minutes)

    async def set_high_frequency_mode(self, enabled: bool) -> None:
        """Enable or disable high-frequency mode."""
        _LOGGER.info("High-frequency mode %s", "enabled" if enabled else "disabled")
        self._high_frequency_mode = enabled

        if enabled:
            # Request an immediate location update from the device
            _LOGGER.info("Requesting immediate location update from device...")
            try:
                success = await self.api.request_location(provider="all")
                if success:
                    _LOGGER.info(
                        "Location request sent. Waiting 10 seconds for device response..."
                    )

                    await asyncio.sleep(10)

                    # Fetch the updated location
                    await self.async_update()
                    self.async_write_ha_state()
                    _LOGGER.info("Initial high-frequency location update completed")
                else:
                    _LOGGER.warning("Failed to request location from device")
            except Exception:
                _LOGGER.exception("Error requesting location in high-frequency mode")

            # Switch to high-frequency polling interval
            self.set_polling_interval(self._high_frequency_interval)
        else:
            # Switch back to normal polling interval
            self.set_polling_interval(self._normal_interval)

    async def async_will_remove_from_hass(self) -> None:
        """Clean up when entity is removed."""
        if self._remove_timer:
            self._remove_timer()
            self._remove_timer = None

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return f"fmd_{self._entry.data['id']}"

    @property
    def device_info(self) -> dict[str, Any]:
        """Return device info to link entities together."""
        return {
            "identifiers": {(DOMAIN, self._entry.entry_id)},
            "name": f"FMD {self._entry.data['id']}",
            "manufacturer": "FMD",
            "model": "Device Tracker",
        }

    @property
    def latitude(self) -> float | None:
        """Return latitude value of the device."""
        return self._location.get("lat") if self._location else None

    @property
    def longitude(self) -> float | None:
        """Return longitude value of the device."""
        return self._location.get("lon") if self._location else None

    @property
    def source_type(self) -> SourceType:
        """Return the source type, eg gps or router, of the device."""
        return SourceType.GPS

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return entity specific state attributes."""
        attributes: dict[str, Any] = {}

        if self._battery_level is not None:
            attributes["battery_level"] = self._battery_level

        # Add timestamp when we polled the FMD server
        if self._last_poll_time is not None:
            attributes["last_poll_time"] = self._last_poll_time

        # Add other location metadata if available
        location = self._location
        if location:
            if "provider" in location:
                attributes["provider"] = location["provider"]

            # Time when FMD client sent location to server (human-readable)
            if "time" in location:
                attributes["device_timestamp"] = location["time"]

            # Unix timestamp (milliseconds) when FMD client sent location to server
            # Store as string to prevent comma formatting in UI
            if "date" in location:
                attributes["device_timestamp_ms"] = str(location["date"])

            # GPS accuracy in meters (optional)
            if "accuracy" in location:
                accuracy = location["accuracy"]
                if self._use_imperial:
                    attributes["gps_accuracy"] = round(accuracy * METERS_TO_FEET, 1)
                    attributes["gps_accuracy_unit"] = "ft"
                else:
                    attributes["gps_accuracy"] = accuracy
                    attributes["gps_accuracy_unit"] = "m"

            # Altitude in meters (optional)
            if "altitude" in location:
                altitude = location["altitude"]
                if self._use_imperial:
                    attributes["altitude"] = round(altitude * METERS_TO_FEET, 1)
                    attributes["altitude_unit"] = "ft"
                else:
                    attributes["altitude"] = altitude
                    attributes["altitude_unit"] = "m"

            # Speed in m/s - only present when moving (optional)
            if "speed" in location:
                speed = location["speed"]
                if self._use_imperial:
                    attributes["speed"] = round(speed * MPS_TO_MPH, 1)
                    attributes["speed_unit"] = "mph"
                else:
                    attributes["speed"] = round(speed, 1)
                    attributes["speed_unit"] = "m/s"

            # Heading/direction 0-360° - only present when moving (optional)
            if "heading" in location:
                attributes["heading"] = location["heading"]

        return attributes

    async def _async_decrypt_data_blob(self, blob: str) -> bytes:
        """Decrypt a data blob in an executor to avoid blocking the event loop.

        Args:
            blob: Base64-encoded encrypted blob from the server

        Returns:
            Decrypted bytes
        """
        return await self.hass.async_add_executor_job(self.api.decrypt_data_blob, blob)

    def _is_location_accurate(self, location_data: dict[str, Any]) -> bool:
        """Determine if a location is accurate based on the provider.

        Accuracy hierarchy (most to least accurate):
        1. fused - Android Fused Location Provider (combines GPS, WiFi, cell,
           sensors - highly accurate)
        2. gps - Direct GPS satellite positioning (highly accurate)
        3. network - Cell tower + WiFi triangulation (moderate accuracy)
        4. BeaconDB - WiFi beacon database lookup (least accurate, often
           blocked)

        Returns True if location is considered accurate, False otherwise.
        """
        provider = str(location_data.get("provider", "")).lower()

        # Fused, GPS, and network are considered accurate
        if provider in ("fused", "gps", "network"):
            return True

        # BeaconDB and unknown providers are considered inaccurate
        if provider in ("beacondb", ""):
            return False

        # For any other unknown providers, log a warning and consider them inaccurate
        _LOGGER.warning(
            "Unknown location provider '%s', treating as inaccurate", provider
        )
        return False

    async def async_update(self) -> None:
        """Update the device location."""
        try:
            _LOGGER.info("=== Starting location update ===")

            # Record the time when we're polling the FMD server
            poll_time = dt_util.now()

            # If filtering is enabled, fetch multiple recent locations to handle cases
            # where the most recent location is inaccurate (e.g., BeaconDB) but a slightly
            # older accurate location (e.g., GPS) exists. If filtering is disabled, just
            # fetch the most recent location.
            num_locations_to_check = 5 if self._block_inaccurate else 1

            _LOGGER.debug(
                "Fetching up to %d recent location(s) (filtering %s)...",
                num_locations_to_check,
                "enabled" if self._block_inaccurate else "disabled",
            )
            location_blobs = await self.api.get_locations(num_locations_to_check)
            _LOGGER.info("=== Received {len(location_blobs)} location blob(s) ===")
            _LOGGER.debug(
                "Received %d location blobs",
                len(location_blobs) if location_blobs else 0,
            )

            if location_blobs:
                selected_location: dict[str, Any] | None = None

                # Decrypt and check each location blob, most recent first
                for idx, blob in enumerate(location_blobs):
                    _LOGGER.debug(
                        "Checking location blob %d/%d (type: %s, length: %d)",
                        idx + 1,
                        len(location_blobs),
                        type(blob).__name__,
                        len(blob) if blob else 0,
                    )

                    if not blob:
                        _LOGGER.warning("Empty blob at index %d", idx)
                        continue

                    # Decrypt and parse the location blob (run in executor to avoid blocking)
                    _LOGGER.debug("Decrypting location blob %d...", idx)
                    decrypted_bytes = await self._async_decrypt_data_blob(blob)
                    location_data: dict[str, Any] = json.loads(decrypted_bytes)

                    provider = location_data.get("provider", "unknown")
                    _LOGGER.debug("Location %d: provider=%s", idx, provider)

                    # If filtering is disabled, use the first (most recent) location
                    if not self._block_inaccurate:
                        _LOGGER.debug(
                            "Filtering disabled, using most recent location (index %d)",
                            idx,
                        )
                        selected_location = location_data
                        break

                    # If filtering is enabled, look for the most recent accurate location
                    if self._is_location_accurate(location_data):
                        _LOGGER.info(
                            "Found accurate location at index %d (provider: %s)",
                            idx,
                            provider,
                        )
                        selected_location = location_data
                        break
                    _LOGGER.debug(
                        "Location %d from provider '%s' is inaccurate, checking next...",
                        idx,
                        provider,
                    )

                # Check if we found a suitable location
                if selected_location:
                    self._location = selected_location
                    provider = selected_location.get("provider", "unknown")
                    _LOGGER.debug("Using location from provider: %s", provider)

                    # Store the poll time (when we queried the server)
                    self._last_poll_time = poll_time.isoformat()

                    # Update battery level when location is updated
                    if "bat" in selected_location:
                        try:
                            self._battery_level = int(selected_location["bat"])
                            _LOGGER.debug("Battery level: %s%%", self._battery_level)
                        except ValueError, TypeError:
                            _LOGGER.warning(
                                "Invalid battery value: %s",
                                selected_location.get("bat"),
                            )
                            self._battery_level = None

                    _LOGGER.info(
                        "Updated location: lat=%s, lon=%s, battery=%s%%, time=%s",
                        selected_location.get("lat"),
                        selected_location.get("lon"),
                        self._battery_level,
                        selected_location.get("time"),
                    )
                else:
                    _LOGGER.warning(
                        "No accurate locations found in the %d most recent "
                        "location(s). Keeping previous location. Toggle "
                        "'Allow Inaccurate Locations' to accept all locations.",
                        len(location_blobs),
                    )
            else:
                # Empty list is OK - device may not have reported location yet
                _LOGGER.info("No location data available from server (empty list)")

        except AuthenticationError as e:
            _LOGGER.error("Authentication error getting location: %s", e)
            # Trigger reauth flow
            raise ConfigEntryAuthFailed(f"Authentication failed: {e}") from e

        except OperationError as e:
            _LOGGER.warning(
                "Connection or API error getting location: %s - Will retry on next poll",
                e,
            )
            # Keep previous location, will retry automatically

        except FmdApiException as e:
            _LOGGER.error("FMD API error getting location: %s", e)
            # Keep previous location, will retry automatically

        except Exception:
            _LOGGER.exception("Unexpected error getting location")
            # Keep previous location, will retry automatically
