"""Support for Ambee."""
from __future__ import annotations

from ambee import AirQuality, Ambee, AmbeeAuthenticationError, Pollen

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, LOGGER, SCAN_INTERVAL, SERVICE_AIR_QUALITY, SERVICE_POLLEN

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Ambee from a config entry."""
    hass.data.setdefault(DOMAIN, {}).setdefault(entry.entry_id, {})

    client = Ambee(
        api_key=entry.data[CONF_API_KEY],
        latitude=entry.data[CONF_LATITUDE],
        longitude=entry.data[CONF_LONGITUDE],
    )

    async def update_air_quality() -> AirQuality:
        """Update method for updating Ambee Air Quality data."""
        try:
            return await client.air_quality()
        except AmbeeAuthenticationError as err:
            raise ConfigEntryAuthFailed from err

    air_quality: DataUpdateCoordinator[AirQuality] = DataUpdateCoordinator(
        hass,
        LOGGER,
        name=f"{DOMAIN}_{SERVICE_AIR_QUALITY}",
        update_interval=SCAN_INTERVAL,
        update_method=update_air_quality,
    )
    await air_quality.async_config_entry_first_refresh()
    hass.data[DOMAIN][entry.entry_id][SERVICE_AIR_QUALITY] = air_quality

    async def update_pollen() -> Pollen:
        """Update method for updating Ambee Pollen data."""
        try:
            return await client.pollen()
        except AmbeeAuthenticationError as err:
            raise ConfigEntryAuthFailed from err

    pollen: DataUpdateCoordinator[Pollen] = DataUpdateCoordinator(
        hass,
        LOGGER,
        name=f"{DOMAIN}_{SERVICE_POLLEN}",
        update_interval=SCAN_INTERVAL,
        update_method=update_pollen,
    )
    await pollen.async_config_entry_first_refresh()
    hass.data[DOMAIN][entry.entry_id][SERVICE_POLLEN] = pollen

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Ambee config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        del hass.data[DOMAIN][entry.entry_id]
    return unload_ok
