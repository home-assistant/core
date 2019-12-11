"""The met component."""
from homeassistant.core import Config, HomeAssistant

from .config_flow import MetFlowHandler  # noqa: F401
from .const import DOMAIN  # noqa: F401


async def async_setup(hass: HomeAssistant, config: Config) -> bool:
    """Set up configured Met."""
    return True


async def async_setup_entry(hass, config_entry):
    """Set up Met as config entry."""
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(config_entry, "weather")
    )
    return True


async def async_unload_entry(hass, config_entry):
    """Unload a config entry."""
    await hass.config_entries.async_forward_entry_unload(config_entry, "weather")
    return True
