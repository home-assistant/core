"""DataUpdateCoordinator for FortiOS integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, FORTIOS_RESULTS_MASTER_MAC, SCAN_INTERVAL
from .firewall import FortiOSAPI

_LOGGER = logging.getLogger(__name__)


def _normalize_usage(results: Any) -> dict[str, Any]:
    """Normalize resource usage results from the FortiOS API.

    The API returns each metric as a list with one element, e.g.
    ``{"cpu": [{"current": 2}], "memory": [{"current": 50}]}``.
    This unwraps those single-element lists into plain dicts.
    """
    if not isinstance(results, dict):
        return {}
    normalized: dict[str, Any] = {}
    for key, value in results.items():
        if isinstance(value, list):
            normalized[key] = value[0] if value else {}
        else:
            normalized[key] = value
    return normalized


class FortiOSDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Class to manage fetching FortiOS data."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        api: FortiOSAPI,
    ) -> None:
        """Initialize."""
        self.api = api
        self.serial = entry.unique_id
        self.devices: dict[str, dict[str, Any]] = {}
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
            config_entry=entry,
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from FortiOS."""
        try:
            fortios_devices = await self.api.get("monitor/user/device/query")
            for device in fortios_devices.get("results", []):
                mac = device.get(FORTIOS_RESULTS_MASTER_MAC)
                if not mac:
                    continue
                self.devices[mac] = device

            system_usage = await self.api.get("monitor/system/resource/usage")
            system_status = await self.api.get("monitor/system/status")

            return {
                "devices": self.devices,
                "system_usage": _normalize_usage(system_usage.get("results", {})),
                "system_status": system_status,
            }
        except Exception as err:
            raise UpdateFailed(f"Error communicating with FortiOS API: {err}") from err
