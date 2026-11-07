"""The MAWAQIT integration."""

from mawaqit import AsyncMawaqitClient

from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.httpx_client import get_async_client

from .coordinator import MawaqitConfigEntry, MawaqitCoordinator

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: MawaqitConfigEntry) -> bool:
    """Set up MAWAQIT from a config entry."""
    client = AsyncMawaqitClient(
        token=entry.data[CONF_API_KEY], http_client=get_async_client(hass)
    )
    coordinator = MawaqitCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: MawaqitConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
