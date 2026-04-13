"""Data update coordinator for Grandstream devices."""

from datetime import timedelta
import logging
from typing import Any

from grandstream_home_api import fetch_gds_status, fetch_gns_metrics, process_push_data

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    COORDINATOR_ERROR_THRESHOLD,
    COORDINATOR_UPDATE_INTERVAL,
    DEVICE_TYPE_GNS_NAS,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class GrandstreamCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from Grandstream device."""

    last_update_method: str | None = None

    def __init__(
        self,
        hass: HomeAssistant,
        device_type: str,
        entry: ConfigEntry,
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
        self.device_type = device_type
        self.entry_id = entry.entry_id
        self._error_count = 0
        self._max_errors = COORDINATOR_ERROR_THRESHOLD
        self._discovery_version = discovery_version

    def _get_api(self):
        """Get API instance from config entry runtime_data."""
        if (
            hasattr(self.config_entry, "runtime_data")
            and self.config_entry.runtime_data
        ):
            return self.config_entry.runtime_data.api
        return None

    def _get_device(self):
        """Get device instance from config entry runtime_data."""
        if (
            hasattr(self.config_entry, "runtime_data")
            and self.config_entry.runtime_data
        ):
            return self.config_entry.runtime_data.device
        return None

    def _update_firmware_version(self, version: str | None) -> None:
        """Update device firmware version."""
        if not version:
            return
        device = self._get_device()
        if device:
            device.set_firmware_version(version)
        return

    def _handle_error(self, error_type: str) -> dict[str, Any]:
        """Handle error and return appropriate status."""
        self._error_count += 1
        if self._error_count >= self._max_errors:
            return {error_type: "unavailable"}
        return {error_type: "unknown"}

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from API endpoint (polling)."""
        try:
            api = self._get_api()
            if not api:
                _LOGGER.error("API not available")
                return self._handle_error("phone_status")

            if hasattr(api, "is_ha_control_disabled") and api.is_ha_control_disabled:
                _LOGGER.warning("HA control is disabled on device")
                return self._handle_error("phone_status")

            # GNS NAS device
            if self.device_type == DEVICE_TYPE_GNS_NAS:
                result = await self.hass.async_add_executor_job(fetch_gns_metrics, api)
                if result is None:
                    _LOGGER.error("API call failed (GNS metrics)")
                    return self._handle_error("device_status")

                self._error_count = 0
                self.last_update_method = "poll"
                self._update_firmware_version(
                    result.get("product_version") or self._discovery_version
                )
                return result

            # GDS device
            result = await self.hass.async_add_executor_job(fetch_gds_status, api)
            if result is None:
                _LOGGER.error("API call failed (GDS status)")
                return self._handle_error("phone_status")

            self._error_count = 0
            self.last_update_method = "poll"
            _LOGGER.debug("Device status updated: %s", result["phone_status"])

            # Update firmware version from API or discovery
            self._update_firmware_version(
                result.get("version") or self._discovery_version
            )

            return {
                "phone_status": result["phone_status"],
                "sip_accounts": result["sip_accounts"],
            }

        except (RuntimeError, ValueError, OSError, KeyError) as e:
            _LOGGER.error("Error getting device status: %s", e)
            error_result = self._handle_error("phone_status")
            error_result["sip_accounts"] = []
            return error_result

    async def async_handle_push_data(self, data: dict[str, Any]) -> None:
        """Handle pushed data."""
        try:
            _LOGGER.debug("Received push data: %s", data)
            data = process_push_data(data)
            self.last_update_method = "push"
            self.async_set_updated_data(data)
        except Exception as e:
            _LOGGER.error("Error processing push data: %s", e)
            raise

    def handle_push_data(self, data: dict[str, Any]) -> None:
        """Handle push data synchronously."""
        try:
            _LOGGER.debug("Processing sync push data: %s", data)
            data = process_push_data(data)
            self.last_update_method = "push"
            self.async_set_updated_data(data)
        except Exception as e:
            _LOGGER.error("Error processing sync push data: %s", e)
            raise
