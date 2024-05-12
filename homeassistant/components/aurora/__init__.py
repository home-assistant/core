"""The aurora component."""

from auroranoaa import AuroraForecast

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_THRESHOLD, DEFAULT_THRESHOLD
from .coordinator import AuroraDataUpdateCoordinator

PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR]

AuroraConfigEntry = ConfigEntry[AuroraDataUpdateCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: AuroraConfigEntry) -> bool:
    """Set up Aurora from a config entry."""
    api = AuroraForecast(async_get_clientsession(hass))

    coordinator = AuroraDataUpdateCoordinator(
        hass=hass,
        api=api,
        latitude=entry.data[CONF_LATITUDE],
        longitude=entry.data[CONF_LONGITUDE],
        threshold=entry.options.get(CONF_THRESHOLD, DEFAULT_THRESHOLD),
    )

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: AuroraConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
