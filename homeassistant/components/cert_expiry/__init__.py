"""The cert_expiry component."""

from homeassistant.const import CONF_HOST, CONF_PORT, CONF_VERIFY_SSL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.start import async_at_started

from .const import CONF_CA_CERTIFICATES
from .coordinator import CertExpiryConfigEntry, CertExpiryDataUpdateCoordinator
from .helper import async_get_ssl_context

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: CertExpiryConfigEntry) -> None:
    """Load the saved entities."""
    host: str = entry.data[CONF_HOST]
    port: int = entry.data[CONF_PORT]

    ssl_context = await async_get_ssl_context(
        hass,
        verify_ssl=entry.data.get(CONF_VERIFY_SSL, True),
        ca_certificates=entry.data.get(CONF_CA_CERTIFICATES, ""),
    )
    coordinator = CertExpiryDataUpdateCoordinator(hass, entry, host, port, ssl_context)

    entry.runtime_data = coordinator

    if entry.unique_id is None:
        hass.config_entries.async_update_entry(entry, unique_id=f"{host}:{port}")

    async def _async_finish_startup(_: HomeAssistant) -> None:
        await coordinator.async_refresh()
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    async_at_started(hass, _async_finish_startup)


async def async_unload_entry(hass: HomeAssistant, entry: CertExpiryConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
