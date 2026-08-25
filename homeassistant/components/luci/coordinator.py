"""DataUpdateCoordinator for the OpenWrt (luci) integration."""

from datetime import datetime, timedelta
import logging
from typing import Any, override

from openwrt_luci_rpc import OpenWrtRpc
from openwrt_luci_rpc.exceptions import LuciRpcUnknownError
from requests.exceptions import ConnectionError as RequestsConnectionError

from homeassistant.components.device_tracker import (
    CONF_CONSIDER_HOME,
    DEFAULT_CONSIDER_HOME,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=30)

type LuciConfigEntry = ConfigEntry[LuciCoordinator]


class LuciCoordinator(DataUpdateCoordinator[dict[str, Any]]):
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
        self._devices: dict[str, Any] = {}
        self._last_seen: dict[str, datetime] = {}

    @property
    def consider_home(self) -> timedelta:
        """Return how long a device stays home after the router stops seeing it."""
        return timedelta(
            seconds=self.config_entry.options.get(
                CONF_CONSIDER_HOME, DEFAULT_CONSIDER_HOME.total_seconds()
            )
        )

    @override
    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from the router."""
        try:
            result = await self.hass.async_add_executor_job(
                lambda: self.router.get_all_connected_devices(only_reachable=True)
            )
        except (ConnectionError, RequestsConnectionError, LuciRpcUnknownError) as err:
            raise UpdateFailed(f"Error communicating with router: {err}") from err

        _LOGGER.debug("Luci get_all_connected_devices returned: %s", result)

        now = dt_util.utcnow()
        for device in result:
            self._devices[device.mac] = device
            self._last_seen[device.mac] = now

        # A device missing from the scan keeps its last known details and stays
        # home until consider_home has elapsed, so brief dropouts don't flap.
        consider_home = self.consider_home
        for mac, last_seen in list(self._last_seen.items()):
            if now - last_seen > consider_home:
                del self._last_seen[mac]
                del self._devices[mac]

        return dict(self._devices)
