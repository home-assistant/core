from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import InvalidAuth, RotarexApi
from .const import DOMAIN, PLATFORMS

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Rotarex from a config entry."""
    session = async_get_clientsession(hass)
    api = RotarexApi(session)

    email = entry.data[CONF_EMAIL]
    password = entry.data[CONF_PASSWORD]

    # Store credentials in the API object for re-authentication
    api.set_credentials(email, password)

    try:
        await api.login(email, password)
    except InvalidAuth as err:
        _LOGGER.error("Authentication failed: %s", err)
        return False

    async def async_update_data():
        """Fetch data from API endpoint."""
        try:
            return await api.fetch_tanks()
        except InvalidAuth as err:
            # This will trigger re-authentication within the API call
            _LOGGER.warning("Token expired, attempting to re-login: %s", err)
            return await api.fetch_tanks()
        except Exception as err:
            raise UpdateFailed(f"Error communicating with API: {err}")

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="Rotarex Sensor",
        update_method=async_update_data,
        update_interval=timedelta(minutes=15),
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
