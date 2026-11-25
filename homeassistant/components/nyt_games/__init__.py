"""The NYT Games integration."""

from nyt_games import NYTGamesClient

from homeassistant.const import CONF_TOKEN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .coordinator import NYTGamesConfigEntry, NYTGamesCoordinator

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
]


async def async_setup_entry(hass: HomeAssistant, entry: NYTGamesConfigEntry) -> None:
    """Set up NYTGames from a config entry."""

    client = NYTGamesClient(
        entry.data[CONF_TOKEN], session=async_create_clientsession(hass)
    )

    coordinator = NYTGamesCoordinator(hass, entry, client)

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: NYTGamesConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
