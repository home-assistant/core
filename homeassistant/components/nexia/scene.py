"""Support for Nexia Automations."""

from typing import Any

from homeassistant.components.scene import Scene
from homeassistant.helpers.event import async_call_later

from .const import ATTR_DESCRIPTION, DOMAIN, NEXIA_DEVICE, UPDATE_COORDINATOR
from .entity import NexiaEntity

SCENE_ACTIVATION_TIME = 5


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up automations for a Nexia device."""

    nexia_data = hass.data[DOMAIN][config_entry.entry_id]
    nexia_home = nexia_data[NEXIA_DEVICE]
    coordinator = nexia_data[UPDATE_COORDINATOR]
    entities = []

    # Automation switches
    for automation_id in nexia_home.get_automation_ids():
        automation = nexia_home.get_automation_by_id(automation_id)

        entities.append(NexiaAutomationScene(coordinator, automation))

    async_add_entities(entities, True)


class NexiaAutomationScene(NexiaEntity, Scene):
    """Provides Nexia automation support."""

    def __init__(self, coordinator, automation):
        """Initialize the automation scene."""
        super().__init__(
            coordinator,
            name=automation.name,
            unique_id=automation.automation_id,
        )
        self._automation = automation

    @property
    def extra_state_attributes(self):
        """Return the scene specific state attributes."""
        data = super().extra_state_attributes
        data[ATTR_DESCRIPTION] = self._automation.description
        return data

    @property
    def icon(self):
        """Return the icon of the automation scene."""
        return "mdi:script-text-outline"

    async def async_activate(self, **kwargs: Any) -> None:
        """Activate an automation scene."""
        await self.hass.async_add_executor_job(self._automation.activate)

        async def refresh_callback(_):
            await self.coordinator.async_refresh()

        async_call_later(self.hass, SCENE_ACTIVATION_TIME, refresh_callback)
