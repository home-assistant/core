"""The Kiosker integration."""

from __future__ import annotations

from kiosker import KioskerAPI

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import CONF_API_TOKEN, CONF_SSL, CONF_SSL_VERIFY
from .coordinator import KioskerDataUpdateCoordinator

_PLATFORMS: list[Platform] = [Platform.SENSOR]

# Limit concurrent updates to prevent overwhelming the API
PARALLEL_UPDATES = 1


type KioskerConfigEntry = ConfigEntry[KioskerDataUpdateCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: KioskerConfigEntry) -> bool:
    """Set up Kiosker from a config entry."""
    if KioskerAPI is None:
        raise ConfigEntryNotReady("Kiosker dependency not available")

    api = KioskerAPI(
        host=entry.data[CONF_HOST],
        port=entry.data[CONF_PORT],
        token=entry.data[CONF_API_TOKEN],
        ssl=entry.data.get(CONF_SSL, False),
        verify=entry.data.get(CONF_SSL_VERIFY, False),
    )

    coordinator = KioskerDataUpdateCoordinator(
        hass,
        api,
        entry,
    )

    await coordinator.async_config_entry_first_refresh()

    if not coordinator.last_update_success:
        raise ConfigEntryNotReady

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)

    # Start the polling cycle immediately to avoid initial delay
    await coordinator.async_refresh()

    return True


async def async_unload_entry(hass: HomeAssistant, entry: KioskerConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)
