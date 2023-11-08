from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Config, HomeAssistant


async def async_setup(hass: HomeAssistant, config: Config) -> bool:
    """Read configuration from yaml."""
    pass


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up this integration from config entry."""
    pass


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Handle removal of an entry."""
