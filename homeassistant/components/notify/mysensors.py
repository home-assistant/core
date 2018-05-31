"""
MySensors notification service.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/notify.mysensors/
"""
from homeassistant.components import mysensors
from homeassistant.components.notify import (
    ATTR_TARGET, DOMAIN, BaseNotificationService)


async def async_get_service(hass, config, discovery_info=None):
    """Get the MySensors notification service."""
    new_devices = mysensors.setup_mysensors_platform(
        hass, DOMAIN, discovery_info, MySensorsNotificationDevice)
    if not new_devices:
        return None
    return MySensorsNotificationService(hass)


class MySensorsNotificationDevice(mysensors.MySensorsDevice):
    """Represent a MySensors Notification device."""

    def send_msg(self, msg):
        """Send a message."""
        for sub_msg in [msg[i:i + 25] for i in range(0, len(msg), 25)]:
            # Max mysensors payload is 25 bytes.
            self.gateway.set_child_value(
                self.node_id, self.child_id, self.value_type, sub_msg)

    def __repr__(self):
        """Return the representation."""
        return "<MySensorsNotificationDevice {}>".format(self.name)


class MySensorsNotificationService(BaseNotificationService):
    """Implement a MySensors notification service."""

    # pylint: disable=too-few-public-methods

    def __init__(self, hass):
        """Initialize the service."""
        self.devices = mysensors.get_mysensors_devices(hass, DOMAIN)

    async def async_send_message(self, message="", **kwargs):
        """Send a message to a user."""
        target_devices = kwargs.get(ATTR_TARGET)
        devices = [device for device in self.devices.values()
                   if target_devices is None or device.name in target_devices]

        for device in devices:
            device.send_msg(message)
