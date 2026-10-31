"""Select the devices supported by this Home Assistant integration."""

from zentraly import DeviceModel, get_device_model

from homeassistant.const import Platform


def get_device_platforms(device_id: str) -> frozenset[Platform]:
    """Keep discovery aligned with the scope available in Home Assistant."""
    if get_device_model(device_id) is DeviceModel.ZTTIN:
        return frozenset({Platform.CLIMATE})
    return frozenset()
