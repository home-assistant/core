"""The Tomorrow.io integration."""

from __future__ import annotations

from pytomorrowio import TomorrowioV4

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.weather import DOMAIN as WEATHER_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN
from .coordinator import TomorrowioDataUpdateCoordinator

PLATFORMS = [SENSOR_DOMAIN, WEATHER_DOMAIN]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Tomorrow.io API from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    api_key = entry.data[CONF_API_KEY]
    # If coordinator already exists for this API key, we'll use that, otherwise
    # we have to create a new one
    if not (coordinator := hass.data[DOMAIN].get(api_key)):
        session = async_get_clientsession(hass)
        # we will not use the class's lat and long so we can pass in garbage
        # lats and longs
        api = TomorrowioV4(api_key, 361.0, 361.0, unit_system="metric", session=session)
        coordinator = TomorrowioDataUpdateCoordinator(hass, api)
        hass.data[DOMAIN][api_key] = coordinator

    await coordinator.async_setup_entry(entry)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    )

    api_key = config_entry.data[CONF_API_KEY]
    coordinator: TomorrowioDataUpdateCoordinator = hass.data[DOMAIN][api_key]
    # If this is true, we can remove the coordinator
    if await coordinator.async_unload_entry(config_entry):
        hass.data[DOMAIN].pop(api_key)
        if not hass.data[DOMAIN]:
            hass.data.pop(DOMAIN)

    return unload_ok
