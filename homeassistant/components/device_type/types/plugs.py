"""Plug device types."""

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import Platform
from homeassistant.helpers.device_type import DeviceSlot, DeviceType


class SmartPlug(DeviceType):
    """A plug-in adapter that switches one outlet."""

    outlet = DeviceSlot(Platform.SWITCH, required=True)
    power = DeviceSlot(SensorDeviceClass.POWER)
    energy = DeviceSlot(SensorDeviceClass.ENERGY)
