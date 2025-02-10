"""Support for Fibaro binary sensors."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

from pyfibaro.fibaro_device import DeviceModel

from homeassistant.components.binary_sensor import (
    ENTITY_ID_FORMAT,
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import FibaroConfigEntry
from .entity import FibaroEntity

SENSOR_TYPES = {
    "com.fibaro.floodSensor": ["Flood", "mdi:water", BinarySensorDeviceClass.MOISTURE],
    "com.fibaro.motionSensor": ["Motion", "mdi:run", BinarySensorDeviceClass.MOTION],
    "com.fibaro.doorSensor": ["Door", "mdi:window-open", BinarySensorDeviceClass.DOOR],
    "com.fibaro.windowSensor": [
        "Window",
        "mdi:window-open",
        BinarySensorDeviceClass.WINDOW,
    ],
    "com.fibaro.smokeSensor": ["Smoke", "mdi:smoking", BinarySensorDeviceClass.SMOKE],
    "com.fibaro.FGMS001": ["Motion", "mdi:run", BinarySensorDeviceClass.MOTION],
    "com.fibaro.heatDetector": ["Heat", "mdi:fire", BinarySensorDeviceClass.HEAT],
    "com.fibaro.accelerometer": [
        "Moving",
        "mdi:axis-arrow",
        BinarySensorDeviceClass.MOVING,
    ],
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FibaroConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Perform the setup for Fibaro controller devices."""
    controller = entry.runtime_data
    async_add_entities(
        [
            FibaroBinarySensor(device)
            for device in controller.fibaro_devices[Platform.BINARY_SENSOR]
        ],
        True,
    )


class FibaroBinarySensor(FibaroEntity, BinarySensorEntity):
    """Representation of a Fibaro Binary Sensor."""

    def __init__(self, fibaro_device: DeviceModel) -> None:
        """Initialize the binary_sensor."""
        super().__init__(fibaro_device)
        self.entity_id = ENTITY_ID_FORMAT.format(self.ha_id)
        self._own_extra_state_attributes: Mapping[str, Any] = {}
        self._fibaro_sensor_type = None
        if fibaro_device.type in SENSOR_TYPES:
            self._fibaro_sensor_type = fibaro_device.type
        elif fibaro_device.base_type in SENSOR_TYPES:
            self._fibaro_sensor_type = fibaro_device.base_type
        if self._fibaro_sensor_type:
            self._attr_device_class = cast(
                BinarySensorDeviceClass, SENSOR_TYPES[self._fibaro_sensor_type][2]
            )
            self._attr_icon = SENSOR_TYPES[self._fibaro_sensor_type][1]

    @property
    def extra_state_attributes(self) -> Mapping[str, Any]:
        """Return the extra state attributes of the device."""
        return {**super().extra_state_attributes, **self._own_extra_state_attributes}

    def update(self) -> None:
        """Get the latest data and update the state."""
        super().update()
        if self._fibaro_sensor_type == "com.fibaro.accelerometer":
            # Accelerator sensors have values for the three axis x, y and z
            moving_values = self._get_moving_values()
            self._attr_is_on = self._is_moving(moving_values)
            self._own_extra_state_attributes = self._get_xyz_moving(moving_values)
        else:
            self._attr_is_on = self.current_binary_state

    def _get_xyz_moving(self, moving_values: Mapping[str, Any]) -> Mapping[str, Any]:
        """Return x y z values of the accelerator sensor value."""
        attrs = {}
        for axis_name in ("x", "y", "z"):
            attrs[axis_name] = float(moving_values[axis_name])
        return attrs

    def _is_moving(self, moving_values: Mapping[str, Any]) -> bool:
        """Return that a moving is detected when one axis reports a value."""
        for axis_name in ("x", "y", "z"):
            if float(moving_values[axis_name]) != 0:
                return True
        return False

    def _get_moving_values(self) -> Mapping[str, Any]:
        """Get the moving values of the accelerator sensor in a dict."""
        return self.fibaro_device.value.dict_value()
