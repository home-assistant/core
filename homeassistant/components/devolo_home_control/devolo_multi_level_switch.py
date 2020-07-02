"""Base class for multi level switches in devolo Home Control."""
import logging

from .devolo_device import DevoloDeviceEntity

_LOGGER = logging.getLogger(__name__)


class DevoloMultiLevelSwitchDeviceEntity(DevoloDeviceEntity):
    """Representation of a multi level switch device within devolo Home Control. Something like a dimmer or a thermostat."""

    def __init__(self, homecontrol, device_instance, element_uid):
        """Initialize a multi level switch within devolo Home Control."""
        super().__init__(
            homecontrol=homecontrol,
            device_instance=device_instance,
            element_uid=element_uid,
            name=f"{device_instance.itemName}",
            sync=self._sync,
        )
        self._multi_level_switch_property = device_instance.multi_level_switch_property[
            element_uid
        ]

        self._value = self._multi_level_switch_property.value

    def _sync(self, message):
        """Update the multi level switch state."""
        if message[0] == self._multi_level_switch_property.element_uid:
            self._value = message[1]
        elif message[0].startswith("hdm"):
            self._available = self._device_instance.is_online()
        else:
            _LOGGER.debug("No valid message received: %s", message)
        self.schedule_update_ha_state()
