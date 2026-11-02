"""The JustNimbus integration."""

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed

from .const import PLATFORMS
from .coordinator import JustNimbusConfigEntry, JustNimbusCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: JustNimbusConfigEntry) -> None:
    """Set up JustNimbus from a config entry."""
    if "zip_code" in entry.data:
        coordinator = JustNimbusCoordinator(hass, entry)
    else:
        raise ConfigEntryAuthFailed
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: JustNimbusConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
