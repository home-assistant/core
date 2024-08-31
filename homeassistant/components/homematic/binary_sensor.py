"""Support for HomeMatic binary sensors."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import ATTR_DISCOVER_DEVICES, ATTR_DISCOVERY_TYPE, DISCOVER_BATTERY
from .entity import HMDevice

SENSOR_TYPES_CLASS = {
    "IPShutterContact": BinarySensorDeviceClass.OPENING,
    "IPShutterContactSabotage": BinarySensorDeviceClass.OPENING,
    "MaxShutterContact": BinarySensorDeviceClass.OPENING,
    "Motion": BinarySensorDeviceClass.MOTION,
    "MotionV2": BinarySensorDeviceClass.MOTION,
    "PresenceIP": BinarySensorDeviceClass.MOTION,
    "Remote": None,
    "RemoteMotion": None,
    "ShutterContact": BinarySensorDeviceClass.OPENING,
    "Smoke": BinarySensorDeviceClass.SMOKE,
    "SmokeV2": BinarySensorDeviceClass.SMOKE,
    "TiltSensor": None,
    "WeatherSensor": None,
    "IPContact": BinarySensorDeviceClass.OPENING,
    "MotionIP": BinarySensorDeviceClass.MOTION,
    "MotionIPV2": BinarySensorDeviceClass.MOTION,
    "MotionIPContactSabotage": BinarySensorDeviceClass.MOTION,
    "IPRemoteMotionV2": BinarySensorDeviceClass.MOTION,
}


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the HomeMatic binary sensor platform."""
    if discovery_info is None:
        return

    devices: list[BinarySensorEntity] = []
    for conf in discovery_info[ATTR_DISCOVER_DEVICES]:
        if discovery_info[ATTR_DISCOVERY_TYPE] == DISCOVER_BATTERY:
            devices.append(HMBatterySensor(conf))
        else:
            devices.append(HMBinarySensor(conf))

    add_entities(devices, True)


class HMBinarySensor(HMDevice, BinarySensorEntity):
    """Representation of a binary HomeMatic device."""

    @property
    def is_on(self):
        """Return true if switch is on."""
        if not self.available:
            return False
        return bool(self._hm_get_state())

    @property
    def device_class(self):
        """Return the class of this sensor from DEVICE_CLASSES."""
        # If state is MOTION (Only RemoteMotion working)
        if self._state == "MOTION":
            return BinarySensorDeviceClass.MOTION
        return SENSOR_TYPES_CLASS.get(self._hmdevice.__class__.__name__)

    def _init_data_struct(self):
        """Generate the data dictionary (self._data) from metadata."""
        # Add state to data struct
        if self._state:
            self._data.update({self._state: None})


class HMBatterySensor(HMDevice, BinarySensorEntity):
    """Representation of an HomeMatic low battery sensor."""

    _attr_device_class = BinarySensorDeviceClass.BATTERY

    @property
    def is_on(self):
        """Return True if battery is low."""
        return bool(self._hm_get_state())

    def _init_data_struct(self):
        """Generate the data dictionary (self._data) from metadata."""
        # Add state to data struct
        if self._state:
            self._data.update({self._state: None})
