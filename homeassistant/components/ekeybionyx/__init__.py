"""The Ekey Bionyx integration."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

PLATFORMS: list[Platform] = [Platform.EVENT]


type EkeyBionyxConfigEntry = ConfigEntry


async def async_setup_entry(hass: HomeAssistant, entry: EkeyBionyxConfigEntry) -> None:
    """Set up the Ekey Bionyx config entry."""
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: EkeyBionyxConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
