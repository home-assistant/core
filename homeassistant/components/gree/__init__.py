"""The Gree Climate integration."""

from datetime import datetime, timedelta
from ipaddress import IPv4Address
import logging

from homeassistant.components.network import async_get_ipv4_broadcast_addresses
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_time_interval

from .const import CONF_KNOWN_HOSTS, DISCOVERY_SCAN_INTERVAL
from .coordinator import DiscoveryService, GreeConfigEntry, GreeRuntimeData

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.CLIMATE, Platform.SWITCH]


async def async_setup_entry(hass: HomeAssistant, entry: GreeConfigEntry) -> None:
    """Set up Gree Climate from a config entry."""
    gree_discovery = DiscoveryService(hass, entry)
    entry.runtime_data = GreeRuntimeData(
        discovery_service=gree_discovery, coordinators=[]
    )

    async def _async_scan_update(_now: datetime | None = None) -> None:
        """Scan broadcast addresses and configured targets."""
        target_addresses = await async_get_ipv4_broadcast_addresses(hass)
        target_addresses.update(
            IPv4Address(address) for address in entry.data.get(CONF_KNOWN_HOSTS, [])
        )
        await gree_discovery.discovery.scan(target_addresses=list(target_addresses))

    async def _async_update_listener(
        _hass: HomeAssistant, _entry: GreeConfigEntry
    ) -> None:
        """Scan immediately when configured targets change."""
        await _async_scan_update()

    _LOGGER.debug("Scanning network for Gree devices")
    await _async_scan_update()

    entry.async_on_unload(
        async_track_time_interval(
            hass, _async_scan_update, timedelta(seconds=DISCOVERY_SCAN_INTERVAL)
        )
    )
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: GreeConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
