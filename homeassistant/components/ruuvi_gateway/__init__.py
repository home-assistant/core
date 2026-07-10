"""The Ruuvi Gateway integration."""
# pylint: disable=home-assistant-use-runtime-data  # Uses legacy hass.data[DOMAIN] pattern

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .bluetooth import async_connect_scanner
from .const import DOMAIN
from .coordinator import RuuviGatewayUpdateCoordinator
from .models import RuuviGatewayRuntimeData

_LOGGER = logging.getLogger(DOMAIN)

type RuuviGatewayConfigEntry = ConfigEntry[RuuviGatewayRuntimeData]


async def async_setup_entry(
    hass: HomeAssistant, entry: RuuviGatewayConfigEntry
) -> bool:
    """Set up Ruuvi Gateway from a config entry."""
    coordinator = RuuviGatewayUpdateCoordinator(hass, entry, _LOGGER)
    scanner, unload_scanner = async_connect_scanner(hass, entry, coordinator)
    entry.runtime_data = RuuviGatewayRuntimeData(
        update_coordinator=coordinator,
        scanner=scanner,
    )
    entry.async_on_unload(unload_scanner)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: RuuviGatewayConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, [])
