"""Support for the Swedish weather institute weather service."""
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Config, HomeAssistant

# Have to import for config_flow to work even if they are not used here
from .config_flow import smhi_locations  # noqa: F401
from .const import DOMAIN  # noqa: F401

DEFAULT_NAME = 'smhi'


async def async_setup(hass: HomeAssistant, config: Config) -> bool:
    """Set up configured SMHI."""
    # We allow setup only through config flow type of config
    return True


async def async_setup_entry(
        hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up SMHI forecast as config entry."""
    hass.async_create_task(hass.config_entries.async_forward_entry_setup(
        config_entry, 'weather'))
    return True


async def async_unload_entry(
        hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    await hass.config_entries.async_forward_entry_unload(
        config_entry, 'weather')
    return True
