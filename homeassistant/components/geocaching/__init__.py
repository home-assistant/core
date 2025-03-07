"""The Geocaching integration."""

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.config_entry_oauth2_flow import (
    OAuth2Session,
    async_get_config_entry_implementation,
)

from .coordinator import GeocachingDataUpdateCoordinator

PLATFORMS = [Platform.SENSOR]

type GeocachingConfigEntry = ConfigEntry[GeocachingData]


@dataclass
class GeocachingData:
    """Geocaching data class for passing runtime data along with the ConfigEntry."""

    coordinator: GeocachingDataUpdateCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: GeocachingConfigEntry) -> bool:
    """Set up Geocaching from a config entry."""
    implementation = await async_get_config_entry_implementation(hass, entry)

    oauth_session = OAuth2Session(hass, entry, implementation)
    coordinator = GeocachingDataUpdateCoordinator(
        hass, entry=entry, session=oauth_session
    )

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = GeocachingData(coordinator=coordinator)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
