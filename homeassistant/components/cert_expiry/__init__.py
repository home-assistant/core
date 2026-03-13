"""The cert_expiry component."""

from __future__ import annotations

from homeassistant.const import (
    CONF_CA_DATA,
    CONF_HOST,
    CONF_IGNORE_HOSTNAME,
    CONF_PORT,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.start import async_at_started

from .coordinator import CertExpiryConfigEntry, CertExpiryDataUpdateCoordinator

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: CertExpiryConfigEntry) -> bool:
    """Load the saved entities."""
    host: str = entry.data[CONF_HOST]
    port: int = entry.data[CONF_PORT]
    ignore_hostname: bool = entry.data[CONF_IGNORE_HOSTNAME]
    ca_data: str = entry.data.get(CONF_CA_DATA, "")

    coordinator = CertExpiryDataUpdateCoordinator(
        hass, entry, host, port, ignore_hostname, ca_data
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


async def async_migrate_entry(
    hass: HomeAssistant, entry: CertExpiryConfigEntry
) -> bool:
    """Migrate old entry."""
    if entry.version > 2:
        # This means the user has downgraded from a future version
        return False

    if entry.version == 1:
        new_data = {**entry.data}
        new_data[CONF_IGNORE_HOSTNAME] = False
        new_data[CONF_CA_DATA] = ""
        hass.config_entries.async_update_entry(entry, data=new_data, version=2)

    return True
