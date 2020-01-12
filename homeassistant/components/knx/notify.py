"""Support for KNX/IP notification services."""
import voluptuous as vol
from xknx.devices import Notification as XknxNotification

from homeassistant.components.notify import PLATFORM_SCHEMA, BaseNotificationService
from homeassistant.const import CONF_ADDRESS, CONF_NAME
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv

from . import ATTR_DISCOVER_DEVICES, DATA_KNX

DEFAULT_NAME = "KNX Notify"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_ADDRESS): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


async def async_get_service(hass, config, discovery_info=None):
    """Get the KNX notification service."""
    return (
        async_get_service_discovery(hass, discovery_info)
        if discovery_info is not None
        else async_get_service_config(hass, config)
    )


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


@callback
def async_get_service_config(hass, config):
    """Set up notification for KNX platform configured within platform."""
    notification = XknxNotification(
        hass.data[DATA_KNX].xknx,
        name=config[CONF_NAME],
        group_address=config[CONF_ADDRESS],
    )
    hass.data[DATA_KNX].xknx.devices.add(notification)
    return KNXNotificationService([notification])


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
