"""Support for Nexia Switches."""

from homeassistant.components.switch import SwitchDevice
from homeassistant.const import ATTR_ATTRIBUTION

from .const import (
    ATTR_DESCRIPTION,
    ATTRIBUTION,
    DATA_NEXIA,
    DOMAIN,
    NEXIA_DEVICE,
    UPDATE_COORDINATOR,
)
from .entity import NexiaEntity


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up sensors for a Nexia device."""

    nexia_data = hass.data[DOMAIN][config_entry.entry_id][DATA_NEXIA]
    nexia_home = nexia_data[NEXIA_DEVICE]
    coordinator = nexia_data[UPDATE_COORDINATOR]
    entities = []

    # Automation switches
    for automation_id in nexia_home.get_automation_ids():
        automation = nexia_home.get_automation_by_id(automation_id)

        entities.append(NexiaAutomationSwitch(coordinator, automation))

    async_add_entities(entities, True)


class NexiaAutomationSwitch(NexiaEntity, SwitchDevice):
    """Provides Nexia automation support."""

    def __init__(self, coordinator, automation):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._coordinator = coordinator
        self._automation = automation

    @property
    def unique_id(self):
        """Return the unique id of the automation."""
        # This is the automation unique_id
        return self._automation.automation_id

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._automation.name

    @property
    def device_state_attributes(self):
        """Return the device specific state attributes."""
        return {
            ATTR_ATTRIBUTION: ATTRIBUTION,
            ATTR_DESCRIPTION: self._automation.description,
        }

    @property
    def icon(self):
        """Return the device class of the automations switch."""
        return "mdi:script-text-outline"

    @property
    def is_on(self):
        """Get whether the automation is enabled is in the on state."""
        # These are all momentary activations
        return False

    def turn_on(self, **kwargs) -> None:
        """Activate an automation switch."""
        self._automation.activate()
