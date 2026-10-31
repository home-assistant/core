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
    entry.async_on_unload(entry.add_update_listener(async_update_entry))
    await async_update_entry(hass, entry)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_update_entry(hass: HomeAssistant, entry: GeocachingConfigEntry) -> None:
    """Reload the config entry when its subentries are updated."""
    if (subentry_ids := frozenset(entry.subentries)) != entry.runtime_data.subentry_ids:
        entry.runtime_data.subentry_ids = subentry_ids
        hass.config_entries.async_schedule_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: GeocachingConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
