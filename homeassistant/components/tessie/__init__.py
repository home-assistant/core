"""Tessie integration."""
from datetime import timedelta
import logging

from tessie_api import get_state_of_all_vehicles

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN
from .models import TessieData

TESSIE_SYNC_INTERVAL = 15
PLATFORMS = [Platform.SENSOR]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Tessie config."""
    api_key = entry.data[CONF_API_KEY]
    session = async_get_clientsession(hass)

    async def async_get():
        vehicles = await get_state_of_all_vehicles(
            session=session, api_key=api_key, only_active=False
        )
        return {
            vehicle["vin"]: vehicle["last_state"] for vehicle in vehicles["results"]
        }

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="Tessie",
        update_method=async_get,
        update_interval=timedelta(seconds=TESSIE_SYNC_INTERVAL),
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = TessieData(coordinator, api_key)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Advantage Air Config."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
