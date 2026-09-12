"""The Ruuvi Gateway integration."""

import logging

from homeassistant.components.bluetooth import async_remove_scanner
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
    return True


async def async_remove_entry(
    hass: HomeAssistant, entry: RuuviGatewayConfigEntry
) -> None:
    """Remove a config entry."""
    if mac_address := entry.unique_id:
        async_remove_scanner(hass, mac_address.upper())
