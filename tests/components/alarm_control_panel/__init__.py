"""The tests for Alarm control panel platforms."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant


async def help_async_setup_entry_init(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> None:
    """Set up test config entry."""
    await hass.config_entries.async_forward_entry_setups(
        config_entry, [Platform.ALARM_CONTROL_PANEL]
    )


async def help_async_unload_entry(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> None:
    """Unload test config emntry."""
    await hass.config_entries.async_unload_platforms_or_raise(
        config_entry, [Platform.ALARM_CONTROL_PANEL]
    )
