"""Support for Abode Security System switches."""
import logging

import abodepy.helpers.constants as CONST
import abodepy.helpers.timeline as TIMELINE

from homeassistant.components.switch import SwitchDevice

from . import AbodeAutomation, AbodeDevice
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

DEVICE_TYPES = [CONST.TYPE_SWITCH, CONST.TYPE_VALVE]


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up Abode switch devices."""
    data = hass.data[DOMAIN]

    entities = []

    for device_type in DEVICE_TYPES:
        for device in data.abode.get_devices(generic_type=device_type):
            entities.append(AbodeSwitch(data, device))

    for automation in data.abode.get_automations(generic_type=CONST.TYPE_AUTOMATION):
        entities.append(
            AbodeAutomationSwitch(data, automation, TIMELINE.AUTOMATION_EDIT_GROUP)
        )

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

    def turn_on(self, **kwargs):
        """Turn on the device."""
        self._automation.set_active(True)

    def turn_off(self, **kwargs):
        """Turn off the device."""
        self._automation.set_active(False)

    @property
    def is_on(self):
        """Return True if the binary sensor is on."""
        return self._automation.is_active
