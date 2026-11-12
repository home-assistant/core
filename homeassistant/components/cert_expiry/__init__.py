"""The cert_expiry component."""

from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import CoreState, HomeAssistant
from homeassistant.helpers.start import async_at_started

from .coordinator import CertExpiryConfigEntry, CertExpiryDataUpdateCoordinator

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: CertExpiryConfigEntry) -> None:
    """Load the saved entities."""
    host: str = entry.data[CONF_HOST]
    port: int = entry.data[CONF_PORT]

    coordinator = CertExpiryDataUpdateCoordinator(hass, entry, host, port)

    entry.runtime_data = coordinator

    if entry.unique_id is None:
        hass.config_entries.async_update_entry(entry, unique_id=f"{host}:{port}")

    async def _async_finish_startup(_: HomeAssistant) -> None:
        await coordinator.async_refresh()
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # When already started, async_at_started would run the forward in a task
    # that setup doesn't await, which isn't allowed
    if hass.state is CoreState.running:
        await _async_finish_startup(hass)
    else:
        async_at_started(hass, _async_finish_startup)


async def async_unload_entry(hass: HomeAssistant, entry: CertExpiryConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
