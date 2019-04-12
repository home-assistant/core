"""Support for Abode Security System binary sensors."""
import logging

from homeassistant.components.binary_sensor import BinarySensorDevice

from . import DOMAIN as ABODE_DOMAIN, AbodeAutomation, AbodeDevice

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['abode']


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up a sensor for an Abode device."""
    import abodepy.helpers.constants as CONST
    import abodepy.helpers.timeline as TIMELINE

    data = hass.data[ABODE_DOMAIN]

    device_types = [CONST.TYPE_CONNECTIVITY, CONST.TYPE_MOISTURE,
                    CONST.TYPE_MOTION, CONST.TYPE_OCCUPANCY,
                    CONST.TYPE_OPENING]

    devices = []
    for device in data.abode.get_devices(generic_type=device_types):
        if data.is_excluded(device):
            continue

        devices.append(AbodeBinarySensor(data, device))

    for automation in data.abode.get_automations(
            generic_type=CONST.TYPE_QUICK_ACTION):
        if data.is_automation_excluded(automation):
            continue

        devices.append(AbodeQuickActionBinarySensor(
            data, automation, TIMELINE.AUTOMATION_EDIT_GROUP))

    data.devices.extend(devices)

    add_entities(devices)


class AbodeBinarySensor(AbodeDevice, BinarySensorDevice):
    """A binary sensor implementation for Abode device."""

    @property
    def is_on(self):
        """Return True if the binary sensor is on."""
        return self._device.is_on

    @property
    def device_class(self):
        """Return the class of the binary sensor."""
        return self._device.generic_type


class AbodeQuickActionBinarySensor(AbodeAutomation, BinarySensorDevice):
    """A binary sensor implementation for Abode quick action automations."""

    def trigger(self):
        """Trigger a quick automation."""
        self._automation.trigger()

    @property
    def is_on(self):
        """Return True if the binary sensor is on."""
        return self._automation.is_active
