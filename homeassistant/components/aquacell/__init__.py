"""The Aquacell integration."""

from __future__ import annotations

from aioaquacell import AquacellApi
from aioaquacell.const import Brand

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_BRAND, DOMAIN, SERVICE_FORCE_POLL
from .coordinator import AquacellConfigEntry, AquacellCoordinator

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: AquacellConfigEntry) -> bool:
    """Set up Aquacell from a config entry."""
    session = async_get_clientsession(hass)

    brand = entry.data.get(CONF_BRAND, Brand.AQUACELL)

    aquacell_api = AquacellApi(session, brand)

    coordinator = AquacellCoordinator(hass, entry, aquacell_api)

    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    async def handle_force_poll(call: ServiceCall) -> None:
        """Handle the force_poll service call."""
        await coordinator.async_refresh()

    hass.services.async_register(DOMAIN, SERVICE_FORCE_POLL, handle_force_poll)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: AquacellConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
