"""Support for Abode Security System switches."""
import abodepy.helpers.constants as CONST

from homeassistant.components.switch import SwitchDevice
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from . import AbodeAutomation, AbodeDevice
from .const import DOMAIN

DEVICE_TYPES = [CONST.TYPE_SWITCH, CONST.TYPE_VALVE]

ICON = "mdi:robot"


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up Abode switch devices."""
    data = hass.data[DOMAIN]

    entities = []

    for device_type in DEVICE_TYPES:
        for device in data.abode.get_devices(generic_type=device_type):
            entities.append(AbodeSwitch(data, device))

    for automation in data.abode.get_automations():
        entities.append(AbodeAutomationSwitch(data, automation))

    async_add_entities(entities)


class AbodeSwitch(AbodeDevice, SwitchDevice):
    """Representation of an Abode switch."""

    def turn_on(self, **kwargs):
        """Turn on the device."""
        self._device.switch_on()

    def turn_off(self, **kwargs):
        """Turn off the device."""
        self._device.switch_off()

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._device.is_on


class AbodeAutomationSwitch(AbodeAutomation, SwitchDevice):
    """A switch implementation for Abode automations."""

    async def async_added_to_hass(self):
        """Set up trigger automation service."""
        await super().async_added_to_hass()

        signal = f"abode_trigger_automation_{self.entity_id}"
        async_dispatcher_connect(self.hass, signal, self.trigger)

    def turn_on(self, **kwargs):
        """Enable the automation."""
        if self._automation.enable(True):
            self.schedule_update_ha_state()

    def turn_off(self, **kwargs):
        """Disable the automation."""
        if self._automation.enable(False):
            self.schedule_update_ha_state()

    def trigger(self):
        """Trigger the automation."""
        self._automation.trigger()

    @property
    def is_on(self):
        """Return True if the automation is enabled."""
        return self._automation.is_enabled

    @property
    def icon(self):
        """Return the robot icon to match Home Assistant automations."""
        return ICON
