"""Component for the Portuguese weather service - IPMA."""
from homeassistant.core import Config, HomeAssistant
from .config_flow import IpmaFlowHandler  # noqa
from .const import DOMAIN # noqa

DEFAULT_NAME = 'ipma'


async def async_setup(hass: HomeAssistant, config: Config) -> bool:
    """Set up configured IPMA."""
    return True


async def async_setup_entry(hass, config_entry):
    """Set up IPMA station as config entry."""
    hass.async_create_task(hass.config_entries.async_forward_entry_setup(
        config_entry, 'weather'))
    return True


async def async_unload_entry(hass, config_entry):
    """Unload a config entry."""
    await hass.config_entries.async_forward_entry_unload(
        config_entry, 'weather')
    return True
