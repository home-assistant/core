"""The ATEN PE component."""
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.typing import ConfigType, HomeAssistantType


async def async_setup(hass: HomeAssistantType, config: ConfigType) -> bool:
    """Component setup, do nothing."""
    return True


async def async_setup_entry(hass: HomeAssistantType, entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, SWITCH_DOMAIN)
    )
    return True


async def async_unload_entry(hass: HomeAssistantType, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_forward_entry_unload(entry, SWITCH_DOMAIN)
