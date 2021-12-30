"""The Nightscout integration."""
from asyncio import TimeoutError as AsyncIOTimeoutError
from datetime import timedelta
import logging

from aiohttp import ClientError
from py_nightscout import Api as NightscoutAPI

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_URL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import SLOW_UPDATE_WARNING
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import API, COORDINATOR, DOMAIN

PLATFORMS = [Platform.SENSOR]
_API_TIMEOUT = SLOW_UPDATE_WARNING - 1

SCAN_INTERVAL = timedelta(minutes=5)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Nightscout from a config entry."""
    server_url = entry.data[CONF_URL]
    api_key = entry.data.get(CONF_API_KEY)
    session = async_get_clientsession(hass)
    api = NightscoutAPI(server_url, session=session, api_secret=api_key)
    try:
        status = await api.get_server_status()
    except (ClientError, AsyncIOTimeoutError, OSError) as error:
        raise ConfigEntryNotReady from error

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {API: api}

    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, server_url)},
        manufacturer="Nightscout Foundation",
        name=status.name,
        sw_version=status.version,
        entry_type=dr.DeviceEntryType.SERVICE,
    )

    async def async_update_batteries():
        """Fetch the latest data from Nightscout REST API and update the state of devices batteries."""
        try:
            return await api.get_latest_devices_status()
        except OSError as error:
            _LOGGER.error(
                "Error fetching battery devices status. Failed with %s", error
            )
            raise UpdateFailed(f"Error communicating with API: {error}") from error

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="battery_sensor",
        update_method=async_update_batteries,
        update_interval=SCAN_INTERVAL,
    )

    hass.data[DOMAIN][entry.entry_id][COORDINATOR] = coordinator

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    await coordinator.async_config_entry_first_refresh()

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
