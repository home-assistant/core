"""Support for KNX/IP notification services."""
from typing import List

from xknx.devices import Notification as XknxNotification

from homeassistant.components.notify import BaseNotificationService

from .const import DOMAIN


async def async_get_service(hass, config, discovery_info=None):
    """Get the KNX notification service."""
    notification_devices = []
    for device in hass.data[DOMAIN].xknx.devices:
        if isinstance(device, XknxNotification):
            notification_devices.append(device)
    return (
        KNXNotificationService(notification_devices) if notification_devices else None
    )


class KNXNotificationService(BaseNotificationService):
    """Implement demo notification service."""

    def __init__(self, devices: List[XknxNotification]):
        """Initialize the service."""
        self.devices = devices

    @property
    def targets(self):
        """Return a dictionary of registered targets."""
        ret = {}
        for device in self.devices:
            ret[device.name] = device.name
        return ret

    async def async_send_message(self, message="", **kwargs):
        """Send a notification to knx bus."""
        if "target" in kwargs:
            await self._async_send_to_device(message, kwargs["target"])
        else:
            await self._async_send_to_all_devices(message)

    async def _async_send_to_all_devices(self, message):
        """Send a notification to knx bus to all connected devices."""
        for device in self.devices:
            await device.set(message)

    async def _async_send_to_device(self, message, names):
        """Send a notification to knx bus to device with given names."""
        for device in self.devices:
            if device.name in names:
                await device.set(message)
