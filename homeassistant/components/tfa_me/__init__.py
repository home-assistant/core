"""TFA.me station integration: __init__.py."""

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import TFAmeConfigEntry, TFAmeUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: TFAmeConfigEntry) -> None:
    """Set up a TFA.me station."""

    entry.runtime_data = coordinator = TFAmeUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: TFAmeConfigEntry) -> None:
    """Unload a config entry."""

    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
