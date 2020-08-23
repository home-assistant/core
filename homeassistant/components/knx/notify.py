"""Support for KNX/IP notification services."""
from xknx.devices import Notification as XknxNotification

from homeassistant.components.notify import BaseNotificationService
from homeassistant.core import callback

from . import ATTR_DISCOVER_DEVICES, DATA_KNX


async def async_get_service(hass, config, discovery_info=None):
    """Get the KNX notification service."""
    if discovery_info is not None:
        async_get_service_discovery(hass, discovery_info)


@callback
def async_get_service_discovery(hass, discovery_info):
    """Set up notifications for KNX platform configured via xknx.yaml."""
    notification_devices = []
    for device_name in discovery_info[ATTR_DISCOVER_DEVICES]:
        device = hass.data[DATA_KNX].xknx.devices[device_name]
        notification_devices.append(device)
    return (
        KNXNotificationService(notification_devices) if notification_devices else None
    )


class KNXNotificationService(BaseNotificationService):
    """Implement demo notification service."""

    def __init__(self, devices: XknxNotification):
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
