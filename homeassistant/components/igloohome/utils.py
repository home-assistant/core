"""House utility functions."""

from igloohome_api import DEVICE_TYPE_BRIDGE, GetDeviceInfoResponse


def get_linked_bridge(
    device_id: str, devices: list[GetDeviceInfoResponse]
) -> str | None:
    """Return the ID of the bridge that is linked to the device. None if no bridge is linked."""
    bridges = (bridge for bridge in devices if bridge.type == DEVICE_TYPE_BRIDGE)
    for bridge in bridges:
        if device_id in (
            linked_device.deviceId for linked_device in bridge.linkedDevices
        ):
            return bridge.deviceId
    return None
