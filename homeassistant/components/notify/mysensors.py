"""
MySensors notification service.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/notify.mysensors/
"""
from homeassistant.components import mysensors
from homeassistant.components.notify import (
    ATTR_TARGET, BaseNotificationService)


def get_service(hass, config, discovery_info=None):
    """Get the MySensors notification service."""
    if discovery_info is None:
        return
    platform_devices = []
    gateways = hass.data.get(mysensors.MYSENSORS_GATEWAYS)
    if not gateways:
        return

    for gateway in gateways:
        if float(gateway.protocol_version) < 2.0:
            continue
        pres = gateway.const.Presentation
        set_req = gateway.const.SetReq
        map_sv_types = {
            pres.S_INFO: [set_req.V_TEXT],
        }
        devices = {}
        gateway.platform_callbacks.append(mysensors.pf_callback_factory(
            map_sv_types, devices, MySensorsNotificationDevice))
        platform_devices.append(devices)

    return MySensorsNotificationService(platform_devices)


class MySensorsNotificationDevice(mysensors.MySensorsDeviceEntity):
    """Represent a MySensors Notification device."""

    def send_msg(self, msg):
        """Send a message."""
        for sub_msg in [msg[i:i + 25] for i in range(0, len(msg), 25)]:
            # Max mysensors payload is 25 bytes.
            self.gateway.set_child_value(
                self.node_id, self.child_id, self.value_type, sub_msg)


class MySensorsNotificationService(BaseNotificationService):
    """Implement MySensors notification service."""

    # pylint: disable=too-few-public-methods

    def __init__(self, platform_devices):
        """Initialize the service."""
        self.platform_devices = platform_devices

    def send_message(self, message="", **kwargs):
        """Send a message to a user."""
        target_devices = kwargs.get(ATTR_TARGET)
        devices = []
        for gw_devs in self.platform_devices:
            for device in gw_devs.values():
                if target_devices is None or device.name in target_devices:
                    devices.append(device)

        for device in devices:
            device.send_msg(message)
