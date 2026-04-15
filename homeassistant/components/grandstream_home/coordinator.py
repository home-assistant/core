"""Data update coordinator for Grandstream devices."""

from datetime import timedelta
import logging
from typing import Any

from grandstream_home_api import GDSPhoneAPI, fetch_gds_status

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import COORDINATOR_ERROR_THRESHOLD, COORDINATOR_UPDATE_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class GrandstreamCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from Grandstream device."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        api: GDSPhoneAPI,
        unique_id: str,
        discovery_version: str | None = None,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=COORDINATOR_UPDATE_INTERVAL),
        )
        self.entry_id = entry.entry_id
        self._api = api
        self._unique_id = unique_id
        self._error_count = 0
        self._max_errors = COORDINATOR_ERROR_THRESHOLD
        self._discovery_version = discovery_version

    def _update_firmware_version(self, version: str | None) -> None:
        """Update device firmware version in device info."""
        if not version:
            return

        # Update firmware version in device registry
        device_registry = dr.async_get(self.hass)
        device = device_registry.async_get_device(
            identifiers={(DOMAIN, self._unique_id)}
        )
        if device:
            device_registry.async_update_device(device.id, sw_version=version)
            _LOGGER.debug("Updated firmware version to %s", version)

    def _handle_error(self, error_type: str) -> dict[str, Any]:
        """Handle error and return appropriate status."""
        self._error_count += 1
        if self._error_count >= self._max_errors:
            return {error_type: "unavailable"}
        return {error_type: "unknown"}

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from API endpoint (polling)."""
        try:
            # Fetch data from device (GDS and GSC use same API)
            result = await self.hass.async_add_executor_job(fetch_gds_status, self._api)
            if result is None:
                _LOGGER.error("API call failed (device status)")
                return self._handle_error("phone_status")

            self._error_count = 0
            _LOGGER.debug("Device status updated: %s", result["phone_status"])

            self._update_firmware_version(
                result.get("version") or self._discovery_version
            )

            return {
                "phone_status": result["phone_status"],
            }

        except (RuntimeError, ValueError, OSError, KeyError) as e:
            _LOGGER.error("Error getting device status: %s", e)
            return self._handle_error("phone_status")
