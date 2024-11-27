"""Support for OpenUV switch."""

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import SunscreenReminder
from .const import SUNSCREEN_DOMAIN

async def async_setup_entry(
    hass: HomeAssistant,
    config: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    discovery_info=None,
) -> None:
    """Set up the Sunscreen Reminder switch."""
    reminder = hass.data.get(SUNSCREEN_DOMAIN)
    if not isinstance(reminder, SunscreenReminder):
        return

    async_add_entities([SunscreenReminderSwitch(reminder)])


class SunscreenReminderSwitch(SwitchEntity):
    """Switch to enable/disable the Sunscreen Reminder."""

    def __init__(self, reminder: SunscreenReminder) -> None:
        """Initialize the switch."""
        self._reminder = reminder
        self._is_on = False
        self._attr_name = "Sunscreen Reminder"
        self._attr_unique_id = "sunscreen_reminder_switch"
        self._attr_icon = "mdi:emoticon-cool-outline"

    @property
    def is_on(self) -> bool:
        """Return whether the switch is on."""
        return self._is_on

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        self._is_on = True
        await self._reminder.async_initialize()  # Initialize periodic checks
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        self._is_on = False
        await self._reminder.async_cleanup()  # Clean up periodic task
        self.async_write_ha_state()
