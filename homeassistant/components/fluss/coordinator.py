"""DataUpdateCoordinator for Fluss+ integration."""

from __future__ import annotations

import asyncio
from typing import Any

from fluss_api import (
    FlussApiClient,
    FlussApiClientAuthenticationError,
    FlussApiClientError,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import slugify

from .const import LOGGER, UPDATE_INTERVAL_TIMEDELTA

type FlussConfigEntry = ConfigEntry[FlussDataUpdateCoordinator]

VALID_OPEN_CLOSE_STATUSES = {"Open", "Closed"}


def device_has_cover_status(device_data: dict[str, Any]) -> bool:
    """Return True if the device status contains a valid openCloseStatus."""
    status = device_data.get("status")
    if status is None:
        return False
    return status.get("openCloseStatus") in VALID_OPEN_CLOSE_STATUSES


class FlussDataUpdateCoordinator(DataUpdateCoordinator[dict[str, dict[str, Any]]]):
    """Manages fetching Fluss device data on a schedule."""

    config_entry: FlussConfigEntry

    def __init__(
        self, hass: HomeAssistant, config_entry: FlussConfigEntry, api_key: str
    ) -> None:
        """Initialize the coordinator."""
        self.api = FlussApiClient(api_key, session=async_get_clientsession(hass))
        self._known_device_ids: set[str] = set()
        super().__init__(
            hass,
            LOGGER,
            name=f"Fluss+ ({slugify(api_key[:8])})",
            config_entry=config_entry,
            update_interval=UPDATE_INTERVAL_TIMEDELTA,
        )

    async def _async_update_data(self) -> dict[str, dict[str, Any]]:
        """Fetch data from the Fluss API and return as a dictionary keyed by deviceId."""
        try:
            devices = await self.api.async_get_devices()
        except FlussApiClientAuthenticationError as err:
            raise ConfigEntryAuthFailed(
                f"Authentication failed: {err}"
            ) from err
        except FlussApiClientError as err:
            raise UpdateFailed(f"Error fetching Fluss devices: {err}") from err

        all_devices = devices.get("devices", [])

        # Filter to WiFi-capable devices only
        wifi_devices: list[dict[str, Any]] = []
        for device in all_devices:
            permissions = device.get("userPermissions", {})
            if permissions.get("canUseWiFi"):
                wifi_devices.append(device)
            else:
                LOGGER.debug(
                    "Skipping device %s (%s): canUseWiFi is not enabled",
                    device.get("deviceId"),
                    device.get("deviceName"),
                )

        # Detect devices that disappeared (access revoked)
        current_ids = {d["deviceId"] for d in wifi_devices}
        if self._known_device_ids:
            removed = self._known_device_ids - current_ids
            for device_id in removed:
                LOGGER.warning(
                    "Fluss device %s no longer accessible",
                    device_id,
                )
        self._known_device_ids = current_ids

        statuses = await asyncio.gather(
            *(
                self._async_get_device_status(device["deviceId"])
                for device in wifi_devices
            )
        )

        return {
            device["deviceId"]: {**device, "status": status}
            for device, status in zip(wifi_devices, statuses, strict=True)
        }

    async def _async_get_device_status(self, device_id: str) -> dict[str, Any] | None:
        """Fetch status for a single device, returning None on failure.

        The API returns {"status": {<fields>}}. We unwrap the inner dict
        so callers can access fields like openCloseStatus directly.
        """
        try:
            response = await self.api.async_get_device_status(device_id)
        except FlussApiClientError as err:
            LOGGER.debug("Failed to get status for device %s: %s", device_id, err)
            return None
        if not isinstance(response, dict):
            LOGGER.debug(
                "Unexpected status response type for device %s: %s",
                device_id,
                type(response).__name__,
            )
            return None
        # Unwrap the nested "status" key from the API response
        status = response.get("status", response)
        if isinstance(status, dict):
            return status
        LOGGER.debug(
            "Unexpected nested status type for device %s: %s",
            device_id,
            type(status).__name__,
        )
        return None
