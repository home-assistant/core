"""Background discovery of PowerShades devices."""

from datetime import timedelta
import logging
from typing import Any

from pyowershades import DiscoveredDevice, async_discover_devices as _lib_discover

from homeassistant.components import network
from homeassistant.config_entries import SOURCE_INTEGRATION_DISCOVERY
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import discovery_flow
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.start import async_at_started

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

DISCOVERY_INTERVAL = timedelta(minutes=15)


async def async_discover_devices(hass: HomeAssistant) -> list[DiscoveredDevice]:
    """Discover PowerShades devices on all enabled network adapters."""
    adapters = await network.async_get_adapters(hass)
    addresses = [
        ip_info["address"]
        for adapter in adapters
        if adapter["enabled"]
        for ip_info in adapter["ipv4"]
    ]
    return await _lib_discover(addresses)


@callback
def async_start_discovery(hass: HomeAssistant) -> None:
    """Start periodic background discovery of PowerShades devices."""

    async def _async_scan(*_: Any) -> None:
        devices = await async_discover_devices(hass)
        for device in devices:
            discovery_flow.async_create_flow(
                hass,
                DOMAIN,
                context={"source": SOURCE_INTEGRATION_DISCOVERY},
                data=device,
            )
        # During the scan the "udp master" goes to the discovery system
        # This reclaims it back to the HA coordinator
        for entry in hass.config_entries.async_loaded_entries(DOMAIN):
            hass.async_create_task(entry.runtime_data.async_request_refresh())

    async_at_started(hass, _async_scan)
    async_track_time_interval(
        hass, _async_scan, DISCOVERY_INTERVAL, cancel_on_shutdown=True
    )
