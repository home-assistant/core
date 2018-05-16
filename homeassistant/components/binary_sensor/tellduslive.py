"""
Support for binary sensors using Tellstick Net.

This platform uses the Telldus Live online service.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.tellduslive/

"""
import logging

from homeassistant.components.tellduslive import TelldusLiveEntity
from homeassistant.components.binary_sensor import BinarySensorDevice

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up Tellstick sensors."""
    if discovery_info is None:
        return
    add_devices(
        TelldusLiveSensor(hass, binary_sensor)
        for binary_sensor in discovery_info
    )


class TelldusLiveSensor(TelldusLiveEntity, BinarySensorDevice):
    """Representation of a Tellstick sensor."""

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self.device.is_on
