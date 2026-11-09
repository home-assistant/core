"""The GeoSphere Austria Forecast integration."""

from zamg import NwpClient

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import REQUEST_TIMEOUT, SUBENTRY_TYPE_LOCATION
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

    coordinators: dict[str, GeoSphereAustriaForecastCoordinator] = {}
    for subentry in entry.get_subentries_of_type(SUBENTRY_TYPE_LOCATION):
        coordinator = GeoSphereAustriaForecastCoordinator(hass, entry, subentry, client)
        await coordinator.async_config_entry_first_refresh()
        coordinators[subentry.subentry_id] = coordinator

    entry.runtime_data = coordinators
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def _async_reload_entry(
    hass: HomeAssistant, entry: GeoSphereAustriaForecastConfigEntry
) -> None:
    """Reload so an added or removed location gets its own coordinator."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(
    hass: HomeAssistant, entry: GeoSphereAustriaForecastConfigEntry
) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
