"""The DVLA integration."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_REG_NUMBER
from .coordinator import DVLACoordinator

type DVLAConfigEntry = ConfigEntry[DVLACoordinator]

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: DVLAConfigEntry) -> bool:
    """Set up platform from a config entry."""

    session = async_get_clientsession(hass)

    coordinator = DVLACoordinator(
        hass,
        entry,
        session,
        entry.data[CONF_REG_NUMBER],
    )
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: DVLAConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
