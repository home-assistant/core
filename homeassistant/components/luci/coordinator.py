"""DataUpdateCoordinator for the OpenWrt (luci) integration."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from openwrt_luci_rpc import OpenWrtRpc

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=30)

type LuciConfigEntry = ConfigEntry[LuciCoordinator]


class LuciCoordinator(DataUpdateCoordinator[dict[str, dict[str, Any]]]):
    """Coordinator for fetching connected devices from an OpenWrt router."""

    config_entry: LuciConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: LuciConfigEntry,
        router: OpenWrtRpc,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name="luci",
            update_interval=SCAN_INTERVAL,
        )
        self.router = router

    async def _async_update_data(self) -> dict[str, dict[str, Any]]:
        """Fetch data from the router."""
        try:
            result = await self.hass.async_add_executor_job(
                lambda: self.router.get_all_connected_devices(only_reachable=True)
            )
        except Exception as err:
            raise UpdateFailed(f"Error communicating with router: {err}") from err

        _LOGGER.debug("Luci get_all_connected_devices returned: %s", result)

        devices: dict[str, dict[str, Any]] = {}
        for device in result:
            if (
                hasattr(self.router.router.owrt_version, "release")
                and self.router.router.owrt_version.release
                and self.router.router.owrt_version.release[0] >= 19
                and not device.reachable
            ):
                continue
            devices[device.mac] = device._asdict()

        return devices
