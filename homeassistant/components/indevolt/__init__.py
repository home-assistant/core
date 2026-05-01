"""Home Assistant integration for indevolt device."""

import asyncio

from homeassistant.config_entries import SOURCE_DISCOVERY
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, UDP_DISCOVERY_PORT
from .coordinator import IndevoltConfigEntry, IndevoltCoordinator
from .services import async_setup_services

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup_entry(hass: HomeAssistant, entry: IndevoltConfigEntry) -> bool:
    """Set up indevolt integration entry using given configuration."""
    coordinator = IndevoltCoordinator(hass, entry)

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up UDP discovery listener and services."""

    async def _start_udp_discovery() -> None:
        """Start UDP discovery listener."""
        loop = asyncio.get_running_loop()

        # Create UDP protocol for device discovery
        class UDPDiscoveryProtocol(asyncio.DatagramProtocol):
            def datagram_received(self, data: bytes, addr: tuple) -> None:
                """Handle UDP broadcast from device."""

                host, _port = addr
                hass.async_create_task(
                    hass.config_entries.flow.async_init(
                        DOMAIN,
                        context={"source": SOURCE_DISCOVERY},
                        data={"host": host},
                    )
                )

        # Start the actual UDP listener
        await loop.create_datagram_endpoint(
            UDPDiscoveryProtocol, local_addr=("0.0.0.0", UDP_DISCOVERY_PORT)
        )

    # Start UDP discovery in background & setup services
    hass.async_create_task(_start_udp_discovery())
    await async_setup_services(hass)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: IndevoltConfigEntry) -> bool:
    """Unload a config entry / clean up resources (when integration is removed / reloaded)."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
