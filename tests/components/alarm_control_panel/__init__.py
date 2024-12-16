"""The tests for Alarm control panel platforms."""

from homeassistant.components.alarm_control_panel import (
    DOMAIN as ALARM_CONTROL_PANEL_DOMAIN,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant


async def help_async_setup_entry_init(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> bool:
    """Set up test config entry."""
    await hass.config_entries.async_forward_entry_setups(
        config_entry, [ALARM_CONTROL_PANEL_DOMAIN]
    )
    return True


async def help_async_unload_entry(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> bool:
    """Unload test config emntry."""
    return await hass.config_entries.async_unload_platforms(
        config_entry, [Platform.ALARM_CONTROL_PANEL]
    )
