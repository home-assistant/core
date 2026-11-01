"""The Homevolt integration."""

from homevolt import Homevolt

from homeassistant.const import CONF_HOST, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .coordinator import HomevoltConfigEntry, HomevoltDataUpdateCoordinator

PLATFORMS: list[Platform] = [
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]


async def async_setup_entry(hass: HomeAssistant, entry: HomevoltConfigEntry) -> None:
    """Set up Homevolt from a config entry."""
    host: str = entry.data[CONF_HOST]
    password: str | None = entry.data.get(CONF_PASSWORD)

    websession = async_get_clientsession(hass)
    client = Homevolt(host, password, websession=websession)

    coordinator = HomevoltDataUpdateCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: HomevoltConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)

    await entry.runtime_data.client.close_connection()
