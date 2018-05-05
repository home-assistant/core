"""
Support for HomematicIP binary sensor.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.homematicip_cloud/
"""

import logging

from homeassistant.components.binary_sensor import BinarySensorDevice
from homeassistant.components.homematicip_cloud import (
    HomematicipGenericDevice, DOMAIN as HOMEMATICIP_CLOUD_DOMAIN,
    ATTR_HOME_ID)

DEPENDENCIES = ['homematicip_cloud']

_LOGGER = logging.getLogger(__name__)

ATTR_WINDOW_STATE = 'window_state'
ATTR_EVENT_DELAY = 'event_delay'
ATTR_MOTION_DETECTED = 'motion_detected'
ATTR_ILLUMINATION = 'illumination'

HMIP_OPEN = 'open'


async def async_setup_platform(hass, config, async_add_devices,
                               discovery_info=None):
    """Set up the HomematicIP binary sensor devices."""
    from homematicip.device import (ShutterContact, MotionDetectorIndoor)

    if discovery_info is None:
        return
    home = hass.data[HOMEMATICIP_CLOUD_DOMAIN][discovery_info[ATTR_HOME_ID]]
    devices = []
    for device in home.devices:
        if isinstance(device, ShutterContact):
            devices.append(HomematicipShutterContact(home, device))
        elif isinstance(device, MotionDetectorIndoor):
            devices.append(HomematicipMotionDetector(home, device))

    if devices:
        async_add_devices(devices)


class HomematicipShutterContact(HomematicipGenericDevice, BinarySensorDevice):
    """HomematicIP shutter contact."""

    def __init__(self, home, device):
        """Initialize the shutter contact."""
        super().__init__(home, device)

    @property
    def device_class(self):
        """Return the class of this sensor."""
        return 'door'

    @property
    def is_on(self):
        """Return true if the shutter contact is on/open."""
        if self._device.sabotage:
            return True
        if self._device.windowState is None:
            return None
        return self._device.windowState.lower() == HMIP_OPEN


class HomematicipMotionDetector(HomematicipGenericDevice, BinarySensorDevice):
    """MomematicIP motion detector."""

    def __init__(self, home, device):
        """Initialize the shutter contact."""
        super().__init__(home, device)

    @property
    def device_class(self):
        """Return the class of this sensor."""
        return 'motion'

    @property
    def is_on(self):
        """Return true if motion is detected."""
        if self._device.sabotage:
            return True
        return self._device.motionDetected
