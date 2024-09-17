"""The meteoswiss integration."""

import dataclasses

import meteoswiss_async

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType
from homeassistant.util.hass_dict import HassKey

from .const import DOMAIN
from .coordinator import MeteoSwissDataUpdateCoordinator


@dataclasses.dataclass
class MeteoSwissData:
    """Typed shared data for this component."""

    client: meteoswiss_async.MeteoSwissClient


DOMAIN_KEY: HassKey[MeteoSwissData] = HassKey(DOMAIN)
PLATFORMS: tuple[Platform, ...] = (Platform.WEATHER,)

type MeteoSwissConfigEntry = ConfigEntry[MeteoSwissDataUpdateCoordinator]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the MeteoSwiss integration."""
    # Store a shared client to be reused by all ConfigEntries and Coordinators.
    hass.data[DOMAIN_KEY] = MeteoSwissData(
        client=meteoswiss_async.MeteoSwissClient(session=async_get_clientsession(hass))
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: MeteoSwissConfigEntry) -> bool:
    """Set up meteoswiss from a config entry."""

    coordinator = MeteoSwissDataUpdateCoordinator(
        hass, api_client=hass.data[DOMAIN_KEY].client, config_entry=entry
    )
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: MeteoSwissConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
