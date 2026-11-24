"""The Foreca integration."""

from pyforeca import ForecaApiClient

from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, SUBENTRY_TYPE_LOCATION
from .coordinator import (
    ForecaConfigEntry,
    ForecaLocationCoordinators,
    ForecaObservationCoordinator,
    ForecaUpdateCoordinator,
)
from .services import async_setup_services

PLATFORMS = [Platform.SENSOR, Platform.WEATHER]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Foreca actions."""
    async_setup_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ForecaConfigEntry) -> None:
    """Set up Foreca from a config entry."""
    client = ForecaApiClient(
        entry.data[CONF_API_KEY], session=async_get_clientsession(hass)
    )

    coordinators: dict[str, ForecaLocationCoordinators] = {}
    for subentry in entry.get_subentries_of_type(SUBENTRY_TYPE_LOCATION):
        weather = ForecaUpdateCoordinator(hass, entry, subentry, client)
        await weather.async_config_entry_first_refresh()
        # Station observations are optional: a failed request leaves only the
        # observation sensors unavailable instead of failing the setup.
        observation = ForecaObservationCoordinator(hass, entry, subentry, client)
        await observation.async_refresh()
        coordinators[subentry.subentry_id] = ForecaLocationCoordinators(
            weather=weather, observation=observation
        )

    entry.runtime_data = coordinators
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def _async_reload_entry(hass: HomeAssistant, entry: ForecaConfigEntry) -> None:
    """Reload so an added or removed location gets its own coordinator."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ForecaConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
