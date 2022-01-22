"""Support for Fibaro binary sensors."""
from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import (
    DOMAIN,
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import CONF_DEVICE_CLASS, CONF_ICON
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import FIBARO_DEVICES, FibaroDevice

SENSOR_TYPES = {
    "com.fibaro.floodSensor": ["Flood", "mdi:water", "flood"],
    "com.fibaro.motionSensor": ["Motion", "mdi:run", BinarySensorDeviceClass.MOTION],
    "com.fibaro.doorSensor": ["Door", "mdi:window-open", BinarySensorDeviceClass.DOOR],
    "com.fibaro.windowSensor": [
        "Window",
        "mdi:window-open",
        BinarySensorDeviceClass.WINDOW,
    ],
    "com.fibaro.smokeSensor": ["Smoke", "mdi:smoking", BinarySensorDeviceClass.SMOKE],
    "com.fibaro.FGMS001": ["Motion", "mdi:run", BinarySensorDeviceClass.MOTION],
    "com.fibaro.heatDetector": ["Heat", "mdi:fire", "heat"],
}


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Perform the setup for Fibaro controller devices."""
    if discovery_info is None:
        return

    entities: list[FibaroBinarySensor] = []
    for fibaro_device in hass.data[FIBARO_DEVICES]["binary_sensor"]:
        device_class = None
        icon = None
        if fibaro_device.type in SENSOR_TYPES:
            device_class = SENSOR_TYPES[fibaro_device.type][2]
            icon = SENSOR_TYPES[fibaro_device.type][1]
        elif fibaro_device.baseType in SENSOR_TYPES:
            device_class = SENSOR_TYPES[fibaro_device.baseType][2]
            icon = SENSOR_TYPES[fibaro_device.baseType][1]

        # device_config overrides:
        devconf = fibaro_device.device_config
        device_class = devconf.get(CONF_DEVICE_CLASS, device_class)
        icon = devconf.get(CONF_ICON, icon)

        entity_description = BinarySensorEntityDescription(
            key="binary_sensor",
            name=fibaro_device.friendly_name,
            device_class=device_class,
            icon=icon,
        )

        entities.append(FibaroBinarySensor(fibaro_device, entity_description))

    add_entities(entities, True)


class FibaroBinarySensor(FibaroDevice, BinarySensorEntity):
    """Representation of a Fibaro Binary Sensor."""

    def __init__(
        self, fibaro_device: Any, entity_description: BinarySensorEntityDescription
    ) -> None:
        """Initialize the binary_sensor."""
        super().__init__(fibaro_device)
        self.entity_description = entity_description
        self.entity_id = f"{DOMAIN}.{self.ha_id}"

    def update(self) -> None:
        """Get the latest data and update the state."""
        self._attr_is_on = self.current_binary_state
