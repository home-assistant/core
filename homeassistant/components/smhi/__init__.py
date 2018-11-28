"""
Component for the swedish weather institute weather service.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/smhi/
"""
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Config, HomeAssistant

# Have to import for config_flow to work
# even if they are not used here
from .config_flow import smhi_locations  # noqa: F401
from .const import DOMAIN  # noqa: F401

REQUIREMENTS = ['smhi-pkg==1.0.5']

DEFAULT_NAME = 'smhi'


async def async_setup(hass: HomeAssistant, config: Config) -> bool:
    """Set up configured smhi."""
    # We allow setup only through config flow type of config
    return True


async def async_setup_entry(hass: HomeAssistant,
                            config_entry: ConfigEntry) -> bool:
    """Set up smhi forecast as config entry."""
    hass.async_create_task(hass.config_entries.async_forward_entry_setup(
        config_entry, 'weather'))
    return True


async def async_unload_entry(hass: HomeAssistant,
                             config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    await hass.config_entries.async_forward_entry_unload(
        config_entry, 'weather')
    return True
