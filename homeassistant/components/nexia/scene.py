"""Support for Nexia Automations."""

from typing import Any

from nexia.automation import NexiaAutomation

from homeassistant.components.scene import Scene
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_call_later

from .const import ATTR_DESCRIPTION, DOMAIN
from .coordinator import NexiaDataUpdateCoordinator
from .entity import NexiaEntity

SCENE_ACTIVATION_TIME = 5


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up automations for a Nexia device."""
    coordinator: NexiaDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    nexia_home = coordinator.nexia_home
    async_add_entities(
        NexiaAutomationScene(
            coordinator, nexia_home.get_automation_by_id(automation_id)
        )
        for automation_id in nexia_home.get_automation_ids()
    )


class NexiaAutomationScene(NexiaEntity, Scene):
    """Provides Nexia automation support."""

    _attr_translation_key = "automation"

    def __init__(
        self, coordinator: NexiaDataUpdateCoordinator, automation: NexiaAutomation
    ) -> None:
        """Initialize the automation scene."""
        super().__init__(
            coordinator,
            automation.automation_id,
        )
        self._attr_name = automation.name
        self._automation: NexiaAutomation = automation
        self._attr_extra_state_attributes = {ATTR_DESCRIPTION: automation.description}

    async def async_activate(self, **kwargs: Any) -> None:
        """Activate an automation scene."""
        await self._automation.activate()

        async def refresh_callback(_):
            await self.coordinator.async_refresh()

        async_call_later(self.hass, SCENE_ACTIVATION_TIME, refresh_callback)
