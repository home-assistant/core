"""The LiteLLM integration."""

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import LiteLLMConfigEntry, LiteLLMDataUpdateCoordinator

PLATFORMS = [Platform.CONVERSATION, Platform.STT]


async def async_setup_entry(hass: HomeAssistant, entry: LiteLLMConfigEntry) -> None:
    """Set up LiteLLM from a config entry."""
    coordinator = LiteLLMDataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))


async def _async_update_listener(
    hass: HomeAssistant, entry: LiteLLMConfigEntry
) -> None:
    """Handle update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: LiteLLMConfigEntry) -> None:
    """Unload LiteLLM."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
