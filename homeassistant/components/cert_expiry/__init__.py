"""The cert_expiry component."""

from __future__ import annotations

from homeassistant.const import CONF_HOST, CONF_PORT, CONF_VALIDATE_CERT_FULL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.start import async_at_started

from .coordinator import CertExpiryConfigEntry, CertExpiryDataUpdateCoordinator

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: CertExpiryConfigEntry) -> bool:
    """Load the saved entities."""
    host: str = entry.data[CONF_HOST]
    port: int = entry.data[CONF_PORT]
    # Backwards compatibility
    validate_cert_full: bool = entry.data.get(
        CONF_VALIDATE_CERT_FULL, True
    )

    coordinator = CertExpiryDataUpdateCoordinator(
        hass, entry, host, port, validate_cert_full
    )

    entry.runtime_data = coordinator

    if entry.unique_id is None:
        hass.config_entries.async_update_entry(entry, unique_id=f"{host}:{port}")

    async def _async_finish_startup(_: HomeAssistant) -> None:
        await coordinator.async_refresh()
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    async_at_started(hass, _async_finish_startup)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: CertExpiryConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
