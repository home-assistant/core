"""The Compit integration."""

from compit_inext_api import CannotConnect, CompitApiConnector, InvalidAuth

from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .coordinator import CompitConfigEntry, CompitDataUpdateCoordinator

PLATFORMS = [
    Platform.CLIMATE,
]


async def async_setup_entry(hass: HomeAssistant, entry: CompitConfigEntry) -> bool:
    """Set up Compit from a config entry."""

    session = async_get_clientsession(hass)
    connector = CompitApiConnector(session)
    try:
        connected = await connector.init(
            entry.data[CONF_EMAIL], entry.data[CONF_PASSWORD], hass.config.language
        )
    except CannotConnect as e:
        raise ConfigEntryNotReady(f"Error while connecting to Compit: {e}") from e
    except InvalidAuth as e:
        raise ConfigEntryAuthFailed(
            f"Invalid credentials for {entry.data[CONF_EMAIL]}"
        ) from e

    if not connected:
        raise ConfigEntryAuthFailed("Authentication API error")

    coordinator = CompitDataUpdateCoordinator(hass, entry, connector)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: CompitConfigEntry) -> bool:
    """Unload an entry for the Compit integration."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
