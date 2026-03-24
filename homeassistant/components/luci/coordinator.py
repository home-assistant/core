"""DataUpdateCoordinator for the OpenWrt (luci) integration."""

from __future__ import annotations

from datetime import datetime, timedelta
import logging
from typing import Any

from openwrt_luci_rpc import OpenWrtRpc

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import CONF_CONSIDER_HOME, DEFAULT_CONSIDER_HOME

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
        self._last_seen: dict[str, datetime] = {}

    @property
    def consider_home_seconds(self) -> float:
        """Return the consider_home interval in seconds."""
        return self.config_entry.options.get(
            CONF_CONSIDER_HOME, DEFAULT_CONSIDER_HOME.total_seconds()
        )

    async def _async_update_data(self) -> dict[str, dict[str, Any]]:
        """Fetch data from the router."""
        try:
            result = await self.hass.async_add_executor_job(
                self.router.get_all_connected_devices, True
            )
        except Exception as err:
            raise UpdateFailed(f"Error communicating with router: {err}") from err

        _LOGGER.debug("Luci get_all_connected_devices returned: %s", result)

        now = dt_util.utcnow()
        consider_home = self.consider_home_seconds

        # Build set of currently connected MACs
        active_macs: set[str] = set()
        active_devices: dict[str, dict[str, Any]] = {}
        for device in result:
            if (
                hasattr(self.router.router.owrt_version, "release")
                and self.router.router.owrt_version.release
                and self.router.router.owrt_version.release[0] >= 19
                and not device.reachable
            ):
                continue
            active_macs.add(device.mac)
            active_devices[device.mac] = device._asdict()
            self._last_seen[device.mac] = now

        # Keep recently-seen devices as "home" for consider_home duration
        devices: dict[str, dict[str, Any]] = dict(active_devices)
        for mac, last_seen in list(self._last_seen.items()):
            if mac in active_macs:
                continue
            if (now - last_seen).total_seconds() < consider_home:
                # Device still within consider_home window
                if self.data and mac in self.data:
                    devices[mac] = self.data[mac]
            else:
                # Expired, remove from tracking
                del self._last_seen[mac]

        return devices
