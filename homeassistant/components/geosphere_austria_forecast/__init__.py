"""The GeoSphere Austria Forecast integration."""

from zamg import NwpClient

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util.async_ import gather_with_limited_concurrency

from .const import MAX_PARALLEL_REQUESTS, REQUEST_TIMEOUT, SUBENTRY_TYPE_LOCATION
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

    # Registered first, so a location added while the forecasts load is not missed.
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))

    coordinators = {
        subentry.subentry_id: GeoSphereAustriaForecastCoordinator(
            hass, entry, subentry, client
        )
        for subentry in entry.get_subentries_of_type(SUBENTRY_TYPE_LOCATION)
    }
    # Wait for every refresh to settle, so that none outlives a failed setup.
    results = await gather_with_limited_concurrency(
        MAX_PARALLEL_REQUESTS,
        *(
            coordinator.async_config_entry_first_refresh()
            for coordinator in coordinators.values()
        ),
        return_exceptions=True,
    )
    for result in results:
        if isinstance(result, BaseException):
            raise result

    entry.runtime_data = coordinators
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
