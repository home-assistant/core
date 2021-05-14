"""The manual component."""
from homeassistant.components.alarm_control_panel import DOMAIN as PARENT_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.typing import ConfigType, HomeAssistantType

DOMAIN = "manual"


async def async_setup(hass: HomeAssistantType, config: ConfigType):
    return True


async def async_setup_entry(hass: HomeAssistantType, config_entry: ConfigEntry) -> bool:
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(config_entry, PARENT_DOMAIN)
    )

    return True
