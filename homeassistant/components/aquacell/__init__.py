"""The Aquacell integration."""

from __future__ import annotations

import logging

from aioaquacell import AquacellApi, AquacellApiException, AuthenticationFailed
from aioaquacell.const import Brand

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.service import async_set_service_schema

from .const import CONF_BRAND, DOMAIN, SERVICE_FORCE_POLL
from .coordinator import AquacellConfigEntry, AquacellCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.BUTTON, Platform.SENSOR]


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
        """Handle force poll service."""
        coordinator: AquacellCoordinator = entry.runtime_data
        try:
            await coordinator.async_force_poll()  # NEW
        except (AquacellApiException, AuthenticationFailed, TimeoutError) as err:  # NEW
            _LOGGER.error("Force poll failed: %s", err)  # NEW

    hass.services.async_register(DOMAIN, SERVICE_FORCE_POLL, handle_force_poll)
    service_description = {
        "name": "Force Poll",
        "description": "Force a data poll from the Aquacell API",
        "fields": {},
    }
    async_set_service_schema(hass, DOMAIN, SERVICE_FORCE_POLL, service_description)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: AquacellConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
