"""The wsdot component."""

import wsdot as wsdot_api

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

PLATFORMS = [Platform.SENSOR]


type WsdotConfigEntry = ConfigEntry[wsdot_api.WsdotTravelTimes]


async def async_setup_entry(hass: HomeAssistant, entry: WsdotConfigEntry) -> bool:
    """Set up wsdot as config entry."""
    session = async_get_clientsession(hass)
    api_key = entry.data[CONF_API_KEY]
    wsdot_travel_times = wsdot_api.WsdotTravelTimes(api_key=api_key, session=session)
    try:
        # The only way to validate the provided API key is to request data
        # we don't need the data here, only the non-exception
        await wsdot_travel_times.get_all_travel_times()
    except wsdot_api.WsdotTravelError as api_error:
        raise ConfigEntryError("Bad auth") from api_error
    entry.runtime_data = wsdot_travel_times

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
