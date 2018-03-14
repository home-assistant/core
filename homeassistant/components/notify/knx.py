"""
KNX/IP notification service.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/notify.knx/
"""

import voluptuous as vol

from homeassistant.components.knx import DATA_KNX, ATTR_DISCOVER_DEVICES
from homeassistant.components.notify import PLATFORM_SCHEMA, \
    BaseNotificationService
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv

CONF_ADDRESS = 'address'
DEFAULT_NAME = 'KNX Notify'
DEPENDENCIES = ['knx']

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_ADDRESS): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string
})


async def async_get_service(hass, config, discovery_info=None):
    """Get the KNX notification service."""
    return async_get_service_discovery(hass, discovery_info) \
        if discovery_info is not None else \
        async_get_service_config(hass, config)


@callback
def async_get_service_discovery(hass, discovery_info):
    """Set up notifications for KNX platform configured via xknx.yaml."""
    notification_devices = []
    for device_name in discovery_info[ATTR_DISCOVER_DEVICES]:
        device = hass.data[DATA_KNX].xknx.devices[device_name]
        notification_devices.append(device)
    return \
        KNXNotificationService(notification_devices) \
        if notification_devices else \
        None


@callback
def async_get_service_config(hass, config):
    """Set up notification for KNX platform configured within platform."""
    import xknx
    notification = xknx.devices.Notification(
        hass.data[DATA_KNX].xknx,
        name=config.get(CONF_NAME),
        group_address=config.get(CONF_ADDRESS))
    hass.data[DATA_KNX].xknx.devices.add(notification)
    return KNXNotificationService([notification, ])


class KNXNotificationService(BaseNotificationService):
    """Implement demo notification service."""

    def __init__(self, devices):
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
