"""Home Assistant integration for indevolt device."""

from __future__ import annotations

import asyncio

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .coordinator import IndevoltConfigEntry, IndevoltCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]
UDP_DISCOVERY_PORT = 8099

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up UDP discovery listener."""
    hass.data.setdefault(DOMAIN, {})

    async def _start_udp_discovery() -> None:
        """Start UDP discovery listener."""
        loop = asyncio.get_event_loop()

        # Create UDP protocol for device discovery
        class UDPDiscoveryProtocol(asyncio.DatagramProtocol):
            def datagram_received(self, data: bytes, addr: tuple) -> None:
                """Handle UDP broadcast from device."""

                host, _port = addr
                hass.async_create_task(
                    hass.config_entries.flow.async_init(
                        DOMAIN,
                        context={"source": "discovery"},
                        data={"host": host},
                    )
                )

        # Start the actual UDP listener
        transport = await loop.create_datagram_endpoint(
            UDPDiscoveryProtocol, local_addr=("0.0.0.0", UDP_DISCOVERY_PORT)
        )

        hass.data[DOMAIN]["transport"] = transport

    # Start UDP discovery in background
    hass.async_create_task(_start_udp_discovery())

    return True


async def async_setup_entry(hass: HomeAssistant, entry: IndevoltConfigEntry) -> bool:
    """Set up indevolt integration entry using given configuration."""
    # Setup coordinator and perform initial data refresh
    coordinator = IndevoltCoordinator(hass, entry)
    await coordinator.async_initialize()

    # Store coordinator in runtime_data
    entry.runtime_data = coordinator

    # Setup platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Perform single refresh after all platforms have registered their contexts
    await coordinator.async_config_entry_first_refresh()

    return True


async def async_unload_entry(hass: HomeAssistant, entry: IndevoltConfigEntry) -> bool:
    """Unload a config entry / clean up resources (when integration is removed / reloaded)."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
