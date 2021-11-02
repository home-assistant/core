"""Support for HUE sensors."""
from __future__ import annotations

from typing import Union

from aiohue.v2.controllers.events import EventType
from aiohue.v2.controllers.sensors import (
    DevicePowerController,
    LightLevelController,
    SensorsController,
    TemperatureController,
)
from aiohue.v2.models.device_power import DevicePower
from aiohue.v2.models.light_level import LightLevel
from aiohue.v2.models.temperature import Temperature

from homeassistant.components.sensor import (
    DOMAIN as SENSOR_DOMAIN,
    STATE_CLASS_MEASUREMENT,
    SensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_ILLUMINANCE,
    DEVICE_CLASS_TEMPERATURE,
    LIGHT_LUX,
    PERCENTAGE,
    TEMP_CELSIUS,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from ..bridge import HueBridge
from ..const import DOMAIN, LOGGER
from .entity import HueBaseEntity

LOGGER = LOGGER.getChild(SENSOR_DOMAIN)

SensorType = Union[DevicePower, LightLevel, Temperature]
ControllerType = Union[
    DevicePowerController, LightLevelController, TemperatureController
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Hue Sensors from Config Entry."""
    bridge: HueBridge = hass.data[DOMAIN][config_entry.entry_id]
    ctrl_base: SensorsController = bridge.api.sensors

    # setup for each sensor-type hue resource
    for controller, sensor_class in (
        (ctrl_base.temperature, HueTemperatureSensor),
        (ctrl_base.light_level, HueLightLevelSensor),
        (ctrl_base.device_power, HueBatterySensor),
    ):

        @callback
        def async_add_sensor(event_type: EventType, resource: SensorType) -> None:
            """Add HUE Sensor."""
            async_add_entities([sensor_class(config_entry, controller, resource)])

        # add all current items in controller
        for sensor in controller:
            async_add_sensor(EventType.RESOURCE_ADDED, sensor)

        # register listener for new sensors
        config_entry.async_on_unload(
            controller.subscribe(
                async_add_sensor, event_filter=EventType.RESOURCE_ADDED
            )
        )


class HueSensorBase(HueBaseEntity, SensorEntity):
    """Representation of a Hue sensor."""

    _attr_state_class = STATE_CLASS_MEASUREMENT

    def __init__(
        self,
        config_entry: ConfigEntry,
        controller: ControllerType,
        resource: SensorType,
    ) -> None:
        """Initialize the light."""
        super().__init__(config_entry, controller, resource)
        self.resource = resource
        self.controller = controller

    @property
    def name(self) -> str:
        """Return sensor name from device name and device class."""
        return f"{self.device.metadata.name}: {self._attr_device_class.title()}"


class HueTemperatureSensor(HueSensorBase):
    """Representation of a Hue Temperature sensor."""

    _attr_native_unit_of_measurement = TEMP_CELSIUS
    _attr_device_class = DEVICE_CLASS_TEMPERATURE

    @property
    def native_value(self) -> float:
        """Return the value reported by the sensor."""
        return round(self.resource.temperature.temperature, 1)


class HueLightLevelSensor(HueSensorBase):
    """Representation of a Hue LightLevel (illuminance) sensor."""

    _attr_native_unit_of_measurement = LIGHT_LUX
    _attr_device_class = DEVICE_CLASS_ILLUMINANCE

    @property
    def native_value(self) -> int:
        """Return the value reported by the sensor."""
        # Light level in 10000 log10 (lux) +1 measured by sensor. Logarithm
        # scale used because the human eye adjusts to light levels and small
        # changes at low lux levels are more noticeable than at high lux
        # levels.
        return round(float(10 ** ((self.resource.light.light_level - 1) / 10000)), 2)


class HueBatterySensor(HueSensorBase):
    """Representation of a Hue Battery sensor."""

    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_device_class = DEVICE_CLASS_BATTERY

    @property
    def native_value(self) -> int:
        """Return the value reported by the sensor."""
        return self.resource.power_state.battery_level
