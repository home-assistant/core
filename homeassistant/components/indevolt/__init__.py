"""Home Assistant integration for indevolt device."""

import asyncio
import logging

from indevolt_api import (
    PASSIVE_DISCOVERY_BIND_ADDR,
    PASSIVE_DISCOVERY_PORT,
    PassiveDiscoveryProtocol,
)

from homeassistant.config_entries import SOURCE_DISCOVERY
from homeassistant.const import EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import Event, HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .coordinator import IndevoltConfigEntry, IndevoltCoordinator
from .services import async_setup_services

_LOGGER = logging.getLogger(__name__)

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

        def _on_device_discovered(host: str) -> None:
            if not hass.config_entries.flow.async_has_matching_discovery_flow(
                DOMAIN, {"source": SOURCE_DISCOVERY}, {"host": host}
            ):
                hass.async_create_task(
                    hass.config_entries.flow.async_init(
                        DOMAIN,
                        context={"source": SOURCE_DISCOVERY},
                        data={"host": host},
                    )
                )

        try:
            transport, _ = await loop.create_datagram_endpoint(
                lambda: PassiveDiscoveryProtocol(_on_device_discovered),
                local_addr=(PASSIVE_DISCOVERY_BIND_ADDR, PASSIVE_DISCOVERY_PORT),
            )

        except OSError as err:
            _LOGGER.warning(
                "Failed to start UDP discovery on port %s: %s",
                PASSIVE_DISCOVERY_PORT,
                err,
            )
            return

        def _close_transport(_event: Event) -> None:
            transport.close()

        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _close_transport)

    # Start UDP discovery in background & setup services
    hass.async_create_task(_start_udp_discovery())
    await async_setup_services(hass)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: IndevoltConfigEntry) -> bool:
    """Unload a config entry / clean up resources (when integration is removed / reloaded)."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
