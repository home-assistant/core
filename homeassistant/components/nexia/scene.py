"""Support for Nexia Automations."""

from homeassistant.components.scene import Scene

from .const import ATTR_DESCRIPTION, DOMAIN, NEXIA_DEVICE, UPDATE_COORDINATOR
from .entity import NexiaEntity


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
            coordinator, name=automation.name, unique_id=automation.automation_id,
        )
        self._automation = automation

    @property
    def device_state_attributes(self):
        """Return the scene specific state attributes."""
        data = super().device_state_attributes
        data.update({ATTR_DESCRIPTION: self._automation.description})
        return data

    @property
    def icon(self):
        """Return the icon of the automation scene."""
        return "mdi:script-text-outline"

    def activate(self):
        """Activate an automation scene."""
        self._automation.activate()
        self._coordinator.async_request_refresh()
