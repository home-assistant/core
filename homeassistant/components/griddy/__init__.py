"""The Griddy Power integration."""
import asyncio
from datetime import timedelta
import logging

from griddypower.async_api import LOAD_ZONES, AsyncGriddy
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import CONF_LOADZONE, DOMAIN, UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.Schema({vol.Required(CONF_LOADZONE): vol.In(LOAD_ZONES)})},
    extra=vol.ALLOW_EXTRA,
)

PLATFORMS = ["sensor"]


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Griddy Power component."""

    hass.data.setdefault(DOMAIN, {})
    conf = config.get(DOMAIN)

    if not conf:
        return True

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data={CONF_LOADZONE: conf.get(CONF_LOADZONE)},
        )
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Griddy Power from a config entry."""

    entry_data = entry.data

    async_griddy = AsyncGriddy(
        aiohttp_client.async_get_clientsession(hass),
        settlement_point=entry_data[CONF_LOADZONE],
    )

    async def async_update_data():
        """Fetch data from API endpoint."""
        return await async_griddy.async_getnow()

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="Griddy getnow",
        update_method=async_update_data,
        update_interval=timedelta(seconds=UPDATE_INTERVAL),
    )

    await coordinator.async_refresh()

    if not coordinator.last_update_success:
        raise ConfigEntryNotReady

    hass.data[DOMAIN][entry.entry_id] = coordinator

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in PLATFORMS
            ]
        )
    )
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
