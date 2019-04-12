"""Support for Abode Security System switches."""
import logging

from homeassistant.components.switch import SwitchDevice

from . import DOMAIN as ABODE_DOMAIN, AbodeAutomation, AbodeDevice

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['abode']


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up Abode switch devices."""
    import abodepy.helpers.constants as CONST
    import abodepy.helpers.timeline as TIMELINE

    data = hass.data[ABODE_DOMAIN]

    devices = []

    # Get all regular switches that are not excluded or marked as lights
    for device in data.abode.get_devices(generic_type=CONST.TYPE_SWITCH):
        if data.is_excluded(device) or data.is_light(device):
            continue

        devices.append(AbodeSwitch(data, device))

    # Get all Abode automations that can be enabled/disabled
    for automation in data.abode.get_automations(
            generic_type=CONST.TYPE_AUTOMATION):
        if data.is_automation_excluded(automation):
            continue

        devices.append(AbodeAutomationSwitch(
            data, automation, TIMELINE.AUTOMATION_EDIT_GROUP))

    data.devices.extend(devices)

    add_entities(devices)


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
