"""The Gaposa integration."""

from __future__ import annotations

from datetime import timedelta
import logging

from pygaposa import FirebaseAuthException, Gaposa, GaposaAuthException

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_PASSWORD, CONF_USERNAME, DOMAIN, UPDATE_INTERVAL
from .coordinator import DataUpdateCoordinatorGaposa

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.COVER]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Gaposa from a config entry."""

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN].setdefault(entry.entry_id, {})

    websession = async_get_clientsession(hass)

    api_key = entry.data[CONF_API_KEY]
    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]

    try:
        gaposa = Gaposa(api_key, loop=hass.loop, websession=websession)
        await gaposa.login(username, password)
    except GaposaAuthException as exp:
        raise ConfigEntryAuthFailed from exp
    except FirebaseAuthException as exp:
        raise ConfigEntryAuthFailed from exp

    coordinator = DataUpdateCoordinatorGaposa(
        hass,
        _LOGGER,
        gaposa,
        # Name of the data. For logging purposes.
        name=entry.title,
        # Polling interval. Will only be polled if there are subscribers.
        update_interval=timedelta(seconds=UPDATE_INTERVAL),
    )

    # Store runtime data that should persist between restarts
    entry.async_on_unload(entry.add_update_listener(update_listener))
    entry.runtime_data = {
        "last_update": None
    }  # Add any runtime data you want to persist

    hass.data[DOMAIN][entry.entry_id] = (gaposa, coordinator)

    # Fetch initial data so we have data when entities subscribe
    await coordinator.async_config_entry_first_refresh()

    # Call async_setup_entry for each of the platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    # Add any code needed to handle configuration updates


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        await hass.data[DOMAIN][entry.entry_id][0].close()
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
