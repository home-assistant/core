"""The GeoSphere Austria Forecast integration."""

from zamg import NwpClient

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import REQUEST_TIMEOUT
from .coordinator import (
    GeoSphereAustriaForecastConfigEntry,
    GeoSphereAustriaForecastCoordinator,
)

PLATFORMS = [Platform.WEATHER]


async def async_setup_entry(
    hass: HomeAssistant, entry: GeoSphereAustriaForecastConfigEntry
) -> None:
    """Set up GeoSphere Austria Forecast from a config entry."""
    client = NwpClient(session=async_get_clientsession(hass))
    client.request_timeout = REQUEST_TIMEOUT

    coordinator = GeoSphereAustriaForecastCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(
    hass: HomeAssistant, entry: GeoSphereAustriaForecastConfigEntry
) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
