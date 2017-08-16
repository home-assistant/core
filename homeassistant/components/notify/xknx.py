"""
Demo notification service.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/demo/
"""
import asyncio
import voluptuous as vol

from homeassistant.components.xknx import DATA_XKNX
from homeassistant.components.notify import PLATFORM_SCHEMA, \
    BaseNotificationService
from homeassistant.const import CONF_NAME
import homeassistant.helpers.config_validation as cv

CONF_ADDRESS = 'address'
DEFAULT_NAME = 'XKNX Notify'
DEPENDENCIES = ['xknx']

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_ADDRESS): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string
})


@asyncio.coroutine
def async_get_service(hass, config, discovery_info=None):
    """Get the XKNX notification service."""
    if DATA_XKNX not in hass.data \
            or not hass.data[DATA_XKNX].initialized:
        return False

    return get_service_from_component(hass) \
        if discovery_info is not None else \
        get_service_from_platform(hass, config)


def get_service_from_component(hass):
    """Set up notifications for XKNX platform configured via xknx.yaml."""
    notification_devices = []
    for device in hass.data[DATA_XKNX].xknx.devices:
        import xknx
        if isinstance(device, xknx.devices.Notification) and \
                not hasattr(device, "already_added_to_hass"):
            notification_devices.append(device)
    return \
        XKNXNotificationService(hass, notification_devices) \
        if len(notification_devices) > 0 else \
        None


def get_service_from_platform(hass, config):
    """Set up notification for XKNX platform configured within plattform."""
    import xknx
    notification = xknx.devices.Notification(
        hass.data[DATA_XKNX].xknx,
        name=config.get(CONF_NAME),
        group_address=config.get(CONF_ADDRESS))
    notification.already_added_to_hass = True
    hass.data[DATA_XKNX].xknx.devices.add(notification)
    return XKNXNotificationService(hass, [notification, ])


class XKNXNotificationService(BaseNotificationService):
    """Implement demo notification service."""

    def __init__(self, hass, devices):
        """Initialize the service."""
        self.hass = hass
        self.devices = devices

    @property
    def targets(self):
        """Return a dictionary of registered targets."""
        ret = {}
        for device in self.devices:
            ret[device.name] = device.name
        return ret

    @asyncio.coroutine
    def async_send_message(self, message="", **kwargs):
        """Send a notification to knx bus."""
        if "target" in kwargs:
            yield from self._async_send_to_device(message, kwargs["target"])
        else:
            yield from self._async_send_to_all_devices(message)

    @asyncio.coroutine
    def _async_send_to_all_devices(self, message):
        """Send a notification to knx bus to all connected devices."""
        for device in self.devices:
            yield from device.set(message)

    @asyncio.coroutine
    def _async_send_to_device(self, message, names):
        """Send a notification to knx bus to device with given names."""
        for device in self.devices:
            if device.name in names:
                yield from device.set(message)
