"""Support for discovering Broadlink devices."""
import asyncio
from datetime import timedelta
from functools import partial
import logging

import broadlink as blk

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_NAME, CONF_TYPE
from homeassistant.core import callback
from homeassistant.helpers import debounce
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import CONF_LOCK, DOMAIN, SUPPORTED_TYPES
from .helpers import get_broadcast_addrs, get_ip_or_none

_LOGGER = logging.getLogger(__name__)


class BroadlinkScout:
    """Manages device discovery."""

    def __init__(self, hass):
        """Initialize the scout."""
        self.hass = hass
        self.timeout = 5
        self.coordinator = DataUpdateCoordinator(
            hass,
            _LOGGER,
            name="discovery",
            update_method=self.async_discover,
            update_interval=timedelta(minutes=15),
            request_refresh_debouncer=debounce.Debouncer(
                hass, _LOGGER, cooldown=self.timeout, immediate=True
            ),
        )
        self.reset_jobs = []

    @property
    def is_on(self):
        """Return True if device discovery is activated."""
        return bool(self.reset_jobs)

    @callback
    def update_listener(self):
        """Create config flows for new devices found."""
        devices = self.coordinator.data
        if not (self.coordinator.last_update_success and devices):
            return

        entries = self.hass.config_entries.async_entries(DOMAIN)
        hosts_and_macs = {
            (get_ip_or_none(entry.data[CONF_HOST]), entry.data[CONF_MAC])
            for entry in entries
        }
        for device in devices:
            host, mac_addr = device.host[0], device.mac.hex()
            if (host, mac_addr) in hosts_and_macs:
                continue

            if device.type not in SUPPORTED_TYPES:
                continue

            self.hass.async_create_task(
                self.hass.config_entries.flow.async_init(
                    DOMAIN,
                    context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
                    data={
                        CONF_HOST: device.host[0],
                        CONF_MAC: device.mac.hex(),
                        CONF_TYPE: device.devtype,
                        CONF_NAME: device.name,
                        CONF_LOCK: device.is_locked,
                    },
                )
            )

    async def async_start(self):
        """Start device discovery."""
        self.reset_jobs.append(
            self.coordinator.async_add_listener(self.update_listener)
        )
        await self.coordinator.async_request_refresh()

    async def async_stop(self):
        """Stop device discovery."""
        while self.reset_jobs:
            self.reset_jobs.pop()()

    async def async_discover(self):
        """Discover Broadlink devices on all available networks."""
        tasks = [
            self.hass.async_add_executor_job(
                partial(blk.discover, timeout=self.timeout, discover_ip_address=addr)
            )
            for addr in get_broadcast_addrs()
        ]
        results = [
            result
            for result in await asyncio.gather(*tasks, return_exceptions=True)
            if not isinstance(result, Exception)
        ]
        return [device for devices in results for device in devices]
