"""The LIFX integration discovery."""

import asyncio
from collections.abc import Collection, Iterable
from datetime import datetime, timedelta
from typing import Any

from lifx import DiscoveredDevice, discover_devices

from homeassistant import config_entries
from homeassistant.components import network
from homeassistant.const import CONF_HOST, EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import HassJob, HomeAssistant, callback
from homeassistant.helpers import discovery_flow
from homeassistant.helpers.event import async_call_later, async_track_time_interval

from .const import CONF_SERIAL, DOMAIN
from .util import normalize_serial

DEFAULT_TIMEOUT = 8.5
DISCOVERY_INTERVAL = timedelta(minutes=15)
DISCOVERY_COOLDOWN = 5


async def async_discover_devices(
    hass: HomeAssistant,
) -> Collection[DiscoveredDevice]:
    """Discover LIFX devices on Home Assistant-selected interfaces."""
    found: dict[str, DiscoveredDevice] = {}

    async def _async_discover_on(broadcast_address: str) -> None:
        """Collect every device answering on one broadcast address."""
        async for discovered in discover_devices(
            timeout=DEFAULT_TIMEOUT, broadcast_address=broadcast_address
        ):
            found[normalize_serial(discovered.serial)] = discovered

    broadcasts = await network.async_get_ipv4_broadcast_addresses(hass)
    # Each sweep holds its socket open for the full timeout, so run them together
    await asyncio.gather(
        *(_async_discover_on(str(broadcast)) for broadcast in broadcasts)
    )
    return found.values()


@callback
def async_init_discovery_flow(hass: HomeAssistant, host: str, serial: str) -> None:
    """Start discovery of a device."""
    discovery_flow.async_create_flow(
        hass,
        DOMAIN,
        context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
        data={CONF_HOST: host, CONF_SERIAL: normalize_serial(serial)},
    )


@callback
def async_trigger_discovery(
    hass: HomeAssistant,
    discovered_devices: Iterable[DiscoveredDevice],
) -> None:
    """Trigger config flows for discovered devices."""
    for device in discovered_devices:
        async_init_discovery_flow(hass, device.ip, device.serial)


class LIFXDiscoveryManager:
    """Manage discovery."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Init the manager."""
        self.hass = hass
        self.lock = asyncio.Lock()

    async def async_discovery(self, *_: Any) -> None:
        """Discover LIFX devices and offer each of them for configuration."""
        async with self.lock:
            if discovered := await async_discover_devices(self.hass):
                async_trigger_discovery(self.hass, discovered)


@callback
def async_setup_discovery(hass: HomeAssistant) -> None:
    """Start periodic discovery."""
    discovery_manager = LIFXDiscoveryManager(hass)

    @callback
    def _async_delayed_discovery(now: datetime) -> None:
        """Start an untracked task to discover devices.

        We do not want the discovery task to block startup.
        """
        hass.async_create_background_task(
            discovery_manager.async_discovery(), "lifx-discovery"
        )

    # Let the system settle a bit before starting discovery
    # to reduce the risk we miss devices because the event
    # loop is blocked at startup.
    async_track_time_interval(
        hass,
        discovery_manager.async_discovery,
        DISCOVERY_INTERVAL,
        cancel_on_shutdown=True,
    )
    async_call_later(
        hass,
        DISCOVERY_COOLDOWN,
        HassJob(_async_delayed_discovery, cancel_on_shutdown=True),
    )
    hass.bus.async_listen_once(
        EVENT_HOMEASSISTANT_STARTED, discovery_manager.async_discovery
    )
