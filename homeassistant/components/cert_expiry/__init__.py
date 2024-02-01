"""The cert_expiry component."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.start import async_at_started

from .const import DOMAIN
from .coordinator import CertExpiryDataUpdateCoordinator

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Load the saved entities."""
    host: str = entry.data[CONF_HOST]
    port: int = entry.data[CONF_PORT]

    coordinator = CertExpiryDataUpdateCoordinator(hass, host, port)

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    if entry.unique_id is None:
        hass.config_entries.async_update_entry(entry, unique_id=f"{host}:{port}")

    async def _async_finish_startup(_: HomeAssistant) -> None:
        await coordinator.async_refresh()
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    async_at_started(hass, _async_finish_startup)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
