"""Support for discovering Broadlink devices."""
from datetime import timedelta
import logging

import broadlink as blk

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_NAME, CONF_TYPE
from homeassistant.core import callback
from homeassistant.helpers import debounce
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import CONF_LOCK, DOMAIN, SUPPORTED_TYPES
from .helpers import get_ip_or_none

_LOGGER = logging.getLogger(__name__)


class BroadlinkDiscovery:
    """Manages device discovery."""

    def __init__(self, hass):
        """Initialize the entity."""
        self.hass = hass
        self.timeout = 5
        self.coordinator = DataUpdateCoordinator(
            hass,
            _LOGGER,
            name="discovery",
            update_method=self.async_discover,
            update_interval=timedelta(minutes=10),
            request_refresh_debouncer=debounce.Debouncer(
                hass, _LOGGER, cooldown=self.timeout, immediate=True
            ),
        )
        self._unsubscribe = None

    async def async_setup(self):
        """Set up device discovery."""
        if self._unsubscribe is None:
            self._unsubscribe = self.coordinator.async_add_listener(self.update)
            await self.coordinator.async_refresh()

    async def async_unload(self):
        """Unload device discovery."""
        if self._unsubscribe is not None:
            self._unsubscribe()
            self._unsubscribe = None

    async def async_discover(self):
        """Discover Broadlink devices on all available networks."""
        hass = self.hass
        broadcast_addrs = hass.data[DOMAIN].config["broadcast_addrs"]
        current_entries = hass.config_entries.async_entries(DOMAIN)

        try:
            await hass.async_add_executor_job(
                self.discover, broadcast_addrs, current_entries
            )
        except OSError:
            pass

    def discover(self, broadcast_addrs, current_entries):
        """Discover Broadlink devices on the given networks, ignoring known devices."""
        known_devices = {
            (get_ip_or_none(entry.data[CONF_HOST]), entry.data[CONF_MAC])
            for entry in current_entries
        }
        for addr in broadcast_addrs:
            for device in blk.xdiscover(discover_ip_address=addr, timeout=self.timeout):
                host, mac_addr = device.host[0], device.mac.hex()
                if (host, mac_addr) in known_devices:
                    continue

                if device.type not in SUPPORTED_TYPES:
                    continue

                self.create_flow(device)

    def create_flow(self, device):
        """Create a configuration flow for a new discovered device."""
        hass = self.hass
        hass.add_job(
            hass.config_entries.flow.async_init(
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

    @callback
    def update(self):
        """Listen for updates.

        This method is only used to activate the update coordinator.
        We do not need a listener because we create flows instantly.
        """
