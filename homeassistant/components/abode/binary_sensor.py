"""Support for Abode Security System binary sensors."""
import logging

import abodepy.helpers.constants as CONST
import abodepy.helpers.timeline as TIMELINE

from homeassistant.components.binary_sensor import BinarySensorDevice
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from . import AbodeAutomation, AbodeDevice
from .const import DOMAIN, SIGNAL_TRIGGER_QUICK_ACTION

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up Abode binary sensor devices."""
    data = hass.data[DOMAIN]

    device_types = [
        CONST.TYPE_CONNECTIVITY,
        CONST.TYPE_MOISTURE,
        CONST.TYPE_MOTION,
        CONST.TYPE_OCCUPANCY,
        CONST.TYPE_OPENING,
    ]

    entities = []

    for device in data.abode.get_devices(generic_type=device_types):
        entities.append(AbodeBinarySensor(data, device))

    for automation in data.abode.get_automations(generic_type=CONST.TYPE_QUICK_ACTION):
        entities.append(
            AbodeQuickActionBinarySensor(
                data, automation, TIMELINE.AUTOMATION_EDIT_GROUP
            )
        )

    async_add_entities(entities)


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

    async def async_added_to_hass(self):
        """Subscribe Abode events."""
        await super().async_added_to_hass()
        signal = SIGNAL_TRIGGER_QUICK_ACTION.format(self.entity_id)
        async_dispatcher_connect(self.hass, signal, self.trigger)

    def trigger(self):
        """Trigger a quick automation."""
        self._automation.trigger()

    @property
    def is_on(self):
        """Return True if the binary sensor is on."""
        return self._automation.is_active
