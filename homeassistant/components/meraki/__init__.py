"""The Meraki integration."""

from contextlib import AsyncExitStack

from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant

from .api import async_create_client
from .coordinator import MerakiConfigEntry, MerakiDataUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.DEVICE_TRACKER]


async def async_setup_entry(hass: HomeAssistant, entry: MerakiConfigEntry) -> None:
    """Set up Meraki from a config entry."""
    # The client only closes its connections when used as a context manager.
    stack = AsyncExitStack()
    entry.async_on_unload(stack.aclose)
    client = await stack.enter_async_context(
        await async_create_client(hass, entry.data[CONF_API_KEY])
    )

    coordinator = MerakiDataUpdateCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: MerakiConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
