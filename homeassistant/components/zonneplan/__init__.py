"""The Zonneplan integration."""

from pyzonneplan import Token, Zonneplan

from homeassistant.const import CONF_EMAIL, CONF_TOKEN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .coordinator import ZonneplanConfigEntry, ZonneplanCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ZonneplanConfigEntry) -> bool:
    """Set up Zonneplan from a config entry."""
    coordinator = ZonneplanCoordinator(
        hass,
        entry,
        Zonneplan(
            email=entry.data[CONF_EMAIL],
            session=async_get_clientsession(hass),
            token=Token.from_dict(entry.data[CONF_TOKEN]),
        ),
    )
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ZonneplanConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
