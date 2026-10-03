"""The V2C integration."""

from pytrydan import Trydan

from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.httpx_client import get_async_client

from .coordinator import V2CConfigEntry, V2CUpdateCoordinator

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.LIGHT,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]


async def async_setup_entry(hass: HomeAssistant, entry: V2CConfigEntry) -> bool:
    """Set up V2C from a config entry."""

    trydan = Trydan(entry.data[CONF_HOST], get_async_client(hass, verify_ssl=False))
    coordinator = V2CUpdateCoordinator(hass, entry, trydan)

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    if coordinator.data.ID and entry.unique_id != coordinator.data.ID:
        hass.config_entries.async_update_entry(entry, unique_id=coordinator.data.ID)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(update_listener))

    return True


async def update_listener(hass: HomeAssistant, entry: V2CConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: V2CConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
