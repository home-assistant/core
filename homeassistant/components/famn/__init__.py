"""The Famn integration."""

from famn_sdk import ApiClient

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import FamnAuth
from .const import BASE_URL
from .coordinator import (
    FamnCalendarsCoordinator,
    FamnChoresCoordinator,
    FamnConfigEntry,
    FamnMealPlanCoordinator,
    FamnRuntimeData,
    FamnScoresCoordinator,
    FamnShoppingCoordinator,
)
from .realtime import FamnRealtime

PLATFORMS: list[Platform] = [
    Platform.CALENDAR,
    Platform.NOTIFY,
    Platform.SENSOR,
    Platform.TODO,
]


async def async_setup_entry(hass: HomeAssistant, entry: FamnConfigEntry) -> bool:
    """Set up Famn from a config entry."""
    client = ApiClient(BASE_URL, session=async_get_clientsession(hass))
    auth = FamnAuth(hass, entry, client)

    chores = FamnChoresCoordinator(hass, entry, auth)
    await chores.async_config_entry_first_refresh()

    calendars = FamnCalendarsCoordinator(hass, entry, auth)
    await calendars.async_config_entry_first_refresh()

    scores = FamnScoresCoordinator(hass, entry, auth)
    await scores.async_config_entry_first_refresh()

    shopping = FamnShoppingCoordinator(hass, entry, auth)
    await shopping.async_config_entry_first_refresh()

    meals = FamnMealPlanCoordinator(hass, entry, auth)
    await meals.async_config_entry_first_refresh()

    entry.runtime_data = FamnRuntimeData(
        chores=chores,
        calendars=calendars,
        scores=scores,
        shopping=shopping,
        meals=meals,
    )

    # Push updates; cancelled by the config entry on unload. Setup does not
    # depend on it succeeding — the coordinators' polling covers outages.
    realtime = FamnRealtime(hass, entry)
    entry.async_create_background_task(hass, realtime.async_run(), "famn-realtime")

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: FamnConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
