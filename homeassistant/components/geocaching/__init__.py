"""The Geocaching integration."""

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.config_entry_oauth2_flow import (
    OAuth2Session,
    async_get_config_entry_implementation,
)

from .coordinator import GeocachingConfigEntry, GeocachingDataUpdateCoordinator

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: GeocachingConfigEntry) -> None:
    """Set up Geocaching from a config entry."""
    implementation = await async_get_config_entry_implementation(hass, entry)

    oauth_session = OAuth2Session(hass, entry, implementation)
    coordinator = GeocachingDataUpdateCoordinator(
        hass, entry=entry, session=oauth_session
    )

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: GeocachingConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
