"""Support for Hue sensors."""
from __future__ import annotations

from typing import Any, Union

from aiohue.v2 import HueBridgeV2
from aiohue.v2.controllers.events import EventType
from aiohue.v2.controllers.sensors import (
    DevicePowerController,
    LightLevelController,
    SensorsController,
    TemperatureController,
    ZigbeeConnectivityController,
)
from aiohue.v2.models.device_power import DevicePower
from aiohue.v2.models.light_level import LightLevel
from aiohue.v2.models.temperature import Temperature
from aiohue.v2.models.zigbee_connectivity import ZigbeeConnectivity

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import LIGHT_LUX, PERCENTAGE, TEMP_CELSIUS
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from ..bridge import HueBridge
from ..const import DOMAIN
from .entity import HueBaseEntity

SensorType = Union[DevicePower, LightLevel, Temperature, ZigbeeConnectivity]
ControllerType = Union[
    DevicePowerController,
    LightLevelController,
    TemperatureController,
    ZigbeeConnectivityController,
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Hue Sensors from Config Entry."""
    bridge: HueBridge = hass.data[DOMAIN][config_entry.entry_id]
    api: HueBridgeV2 = bridge.api
    ctrl_base: SensorsController = api.sensors

    @callback
    def register_items(controller: ControllerType, sensor_class: SensorType):
        @callback
        def async_add_sensor(event_type: EventType, resource: SensorType) -> None:
            """Add Hue Sensor."""
            async_add_entities([sensor_class(bridge, controller, resource)])

        # add all current items in controller
        for sensor in controller:
            async_add_sensor(EventType.RESOURCE_ADDED, sensor)

        # register listener for new sensors
        config_entry.async_on_unload(
            controller.subscribe(
                async_add_sensor, event_filter=EventType.RESOURCE_ADDED
            )
        )

    # setup for each sensor-type hue resource
    register_items(ctrl_base.temperature, HueTemperatureSensor)
    register_items(ctrl_base.light_level, HueLightLevelSensor)
    register_items(ctrl_base.device_power, HueBatterySensor)
    register_items(ctrl_base.zigbee_connectivity, HueZigbeeConnectivitySensor)


class HueSensorBase(HueBaseEntity, SensorEntity):
    """Representation of a Hue sensor."""

    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        bridge: HueBridge,
        controller: ControllerType,
        resource: SensorType,
    ) -> None:
        """Initialize the light."""
        super().__init__(bridge, controller, resource)
        self.resource = resource
        self.controller = controller


class HueTemperatureSensor(HueSensorBase):
    """Representation of a Hue Temperature sensor."""

    _attr_native_unit_of_measurement = TEMP_CELSIUS
    _attr_device_class = SensorDeviceClass.TEMPERATURE

    @property
    def native_value(self) -> float:
        """Return the value reported by the sensor."""
        return round(self.resource.temperature.temperature, 1)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the optional state attributes."""
        return {"temperature_valid": self.resource.temperature.temperature_valid}


class HueLightLevelSensor(HueSensorBase):
    """Representation of a Hue LightLevel (illuminance) sensor."""

    _attr_native_unit_of_measurement = LIGHT_LUX
    _attr_device_class = SensorDeviceClass.ILLUMINANCE

    @property
    def native_value(self) -> int:
        """Return the value reported by the sensor."""
        # Light level in 10000 log10 (lux) +1 measured by sensor. Logarithm
        # scale used because the human eye adjusts to light levels and small
        # changes at low lux levels are more noticeable than at high lux
        # levels.
        return int(10 ** ((self.resource.light.light_level - 1) / 10000))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the optional state attributes."""
        return {
            "light_level": self.resource.light.light_level,
            "light_level_valid": self.resource.light.light_level_valid,
        }


class HueBatterySensor(HueSensorBase):
    """Representation of a Hue Battery sensor."""

    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def native_value(self) -> int:
        """Return the value reported by the sensor."""
        return self.resource.power_state.battery_level

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the optional state attributes."""
        return {"battery_state": self.resource.power_state.battery_state.value}


class HueZigbeeConnectivitySensor(HueSensorBase):
    """Representation of a Hue ZigbeeConnectivity sensor."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False

    @property
    def native_value(self) -> str:
        """Return the value reported by the sensor."""
        return self.resource.status.value

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the optional state attributes."""
        return {"mac_address": self.resource.mac_address}
