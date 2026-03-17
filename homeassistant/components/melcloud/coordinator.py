"""DataUpdateCoordinator for the MELCloud integration."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from aiohttp import ClientConnectionError, ClientResponseError
from pymelcloud import Device
from pymelcloud.atw_device import Zone

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Delay before refreshing after a state change to allow device to process
# and avoid race conditions with rapid sequential changes
REQUEST_REFRESH_DELAY = 1.5

# Default update interval in minutes (matches upstream Throttle value)
DEFAULT_UPDATE_INTERVAL = 15

# Retry interval in seconds for transient failures
RETRY_INTERVAL_SECONDS = 30

# Number of consecutive failures before marking device unavailable
MAX_CONSECUTIVE_FAILURES = 3

type MelCloudConfigEntry = ConfigEntry[dict[str, list[MelCloudDeviceUpdateCoordinator]]]


class MelCloudDeviceUpdateCoordinator(DataUpdateCoordinator[None]):
    """Per-device coordinator for MELCloud data updates."""

    def __init__(
        self,
        hass: HomeAssistant,
        device: Device,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the per-device coordinator."""
        self.device = device
        self.device_available = True
        self._consecutive_failures = 0

        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=f"{DOMAIN}_{device.name}",
            update_interval=timedelta(minutes=DEFAULT_UPDATE_INTERVAL),
            always_update=True,
            request_refresh_debouncer=Debouncer(
                hass,
                _LOGGER,
                cooldown=REQUEST_REFRESH_DELAY,
                immediate=False,
            ),
        )

    @property
    def extra_attributes(self) -> dict[str, Any]:
        """Return extra device attributes."""
        data: dict[str, Any] = {
            "device_id": self.device.device_id,
            "serial": self.device.serial,
            "mac": self.device.mac,
        }
        if (unit_infos := self.device.units) is not None:
            for i, unit in enumerate(unit_infos[:2]):
                data[f"unit_{i}_model"] = unit.get("model")
                data[f"unit_{i}_serial"] = unit.get("serial")
        return data

    @property
    def device_id(self) -> str:
        """Return device ID."""
        return self.device.device_id

    @property
    def building_id(self) -> str:
        """Return building ID of the device."""
        return self.device.building_id

    @property
    def device_info(self) -> DeviceInfo:
        """Return a device description for device registry."""
        model = None
        if (unit_infos := self.device.units) is not None:
            model = ", ".join([x["model"] for x in unit_infos if x["model"]])
        return DeviceInfo(
            connections={(CONNECTION_NETWORK_MAC, self.device.mac)},
            identifiers={(DOMAIN, f"{self.device.mac}-{self.device.serial}")},
            manufacturer="Mitsubishi Electric",
            model=model,
            name=self.device.name,
        )

    def zone_device_info(self, zone: Zone) -> DeviceInfo:
        """Return a zone device description for device registry."""
        dev = self.device
        return DeviceInfo(
            identifiers={(DOMAIN, f"{dev.mac}-{dev.serial}-{zone.zone_index}")},
            manufacturer="Mitsubishi Electric",
            model="ATW zone device",
            name=f"{self.device.name} {zone.name}",
            via_device=(DOMAIN, f"{dev.mac}-{dev.serial}"),
        )

    async def _async_update_data(self) -> None:
        """Fetch data for this specific device from MELCloud."""
        try:
            await self.device.update()
            # Success - reset failure counter and restore normal interval
            if self._consecutive_failures > 0:
                _LOGGER.info(
                    "Connection restored for %s after %d failed attempt(s)",
                    self.device.name,
                    self._consecutive_failures,
                )
                self._consecutive_failures = 0
                self.update_interval = timedelta(minutes=DEFAULT_UPDATE_INTERVAL)
            self.device_available = True
        except ClientResponseError as ex:
            if ex.status in (401, 403):
                raise ConfigEntryAuthFailed from ex
            if ex.status == 429:
                _LOGGER.error(
                    "MELCloud rate limit exceeded for %s. Your account may be "
                    "temporarily blocked",
                    self.device.name,
                )
                # Rate limit - mark unavailable immediately
                self.device_available = False
                raise UpdateFailed(
                    f"Rate limit exceeded for {self.device.name}"
                ) from ex
            # Other HTTP errors - use retry logic
            self._handle_failure(f"Error updating {self.device.name}: {ex}", ex)
        except ClientConnectionError as ex:
            self._handle_failure(f"Connection failed for {self.device.name}: {ex}", ex)

    def _handle_failure(self, message: str, exception: Exception | None = None) -> None:
        """Handle a connection failure with retry logic.

        For transient failures, entities remain available with their last known
        values for up to MAX_CONSECUTIVE_FAILURES attempts. During retries, the
        update interval is shortened to RETRY_INTERVAL_SECONDS for faster recovery.
        After the threshold is reached, entities are marked unavailable.
        """
        self._consecutive_failures += 1

        if self._consecutive_failures < MAX_CONSECUTIVE_FAILURES:
            # Keep entities available with cached data, use shorter retry interval
            _LOGGER.warning(
                "%s (attempt %d/%d, retrying in %ds)",
                message,
                self._consecutive_failures,
                MAX_CONSECUTIVE_FAILURES,
                RETRY_INTERVAL_SECONDS,
            )
            self.update_interval = timedelta(seconds=RETRY_INTERVAL_SECONDS)
        else:
            # Threshold reached - mark unavailable and restore normal interval
            _LOGGER.warning(
                "%s (attempt %d/%d, marking unavailable)",
                message,
                self._consecutive_failures,
                MAX_CONSECUTIVE_FAILURES,
            )
            self.device_available = False
            self.update_interval = timedelta(minutes=DEFAULT_UPDATE_INTERVAL)
            raise UpdateFailed(message) from exception

    async def async_set(self, properties: dict[str, Any]) -> None:
        """Write state changes to the MELCloud API."""
        try:
            await self.device.set(properties)
            self.device_available = True
        except ClientConnectionError:
            _LOGGER.warning("Connection failed for %s", self.device.name)
            self.device_available = False

        await self.async_request_refresh()
