"""DataUpdateCoordinator for the Netis Router integration.

The coordinator is the central polling hub. On each update cycle it calls
``NetisClient.gather()`` which concurrently fetches all router endpoints
(system info, devices, WAN status, LTE signal, WiFi config, LED state),
parses them into a :class:`NetisData` snapshot, and caches it for all
platform entities to read.

If the poll fails (router unreachable, session expired, etc.) the
coordinator raises ``UpdateFailed`` which HA translates into entity state
``unavailable`` and retries with exponential backoff.

The polling interval is configurable via Options Flow (10–300 seconds,
default 30).
"""

from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import NetisClient, NetisData, NetisError
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class NetisCoordinator(DataUpdateCoordinator[NetisData]):
    """Coordinator that polls the router and exposes a typed snapshot.

    Generic over :class:`NetisData` so that ``self.data`` is fully typed for
    all platform entities that consume it.
    """

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialise the coordinator with the configured polling interval."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(
                # User can override via Options Flow (10–300 s, default 30).
                seconds=entry.options.get("scan_interval", DEFAULT_SCAN_INTERVAL)
            ),
        )
        # Build the API client with HA's shared aiohttp session for connection
        # pooling and proper lifecycle management.
        self.client = NetisClient(
            session=async_get_clientsession(hass),
            host=entry.data[CONF_HOST],
            password=entry.data[CONF_PASSWORD],
        )

    async def _async_update_data(self) -> NetisData:
        """Fetch and parse all router data in a single poll cycle.

        On failure, raises :class:`UpdateFailed` so HA marks entities as
        ``unavailable`` and retries with backoff.
        """
        try:
            return await self.client.gather()
        except NetisError as err:
            raise UpdateFailed(str(err)) from err
