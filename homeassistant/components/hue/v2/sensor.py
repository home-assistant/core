"""Support for Hue sensors."""

from __future__ import annotations

from functools import partial
from typing import Any

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

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import LIGHT_LUX, PERCENTAGE, EntityCategory, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from ..bridge import HueBridge
from ..const import DOMAIN
from .entity import HueBaseEntity

type SensorType = DevicePower | LightLevel | Temperature | ZigbeeConnectivity
type ControllerType = (
    DevicePowerController
    | LightLevelController
    | TemperatureController
    | ZigbeeConnectivityController
)


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
        make_sensor_entity = partial(sensor_class, bridge, controller)

        @callback
        def async_add_sensor(event_type: EventType, resource: SensorType) -> None:
            """Add Hue Sensor."""
            async_add_entities([make_sensor_entity(resource)])

        # add all current items in controller
        async_add_entities(make_sensor_entity(sensor) for sensor in controller)

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

    entity_description = SensorEntityDescription(
        key="temperature_sensor",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        has_entity_name=True,
        state_class=SensorStateClass.MEASUREMENT,
    )

    @property
    def native_value(self) -> float:
        """Return the value reported by the sensor."""
        return round(self.resource.temperature.value, 1)


class HueLightLevelSensor(HueSensorBase):
    """Representation of a Hue LightLevel (illuminance) sensor."""

    entity_description = SensorEntityDescription(
        key="lightlevel_sensor",
        device_class=SensorDeviceClass.ILLUMINANCE,
        native_unit_of_measurement=LIGHT_LUX,
        has_entity_name=True,
        state_class=SensorStateClass.MEASUREMENT,
    )

    @property
    def native_value(self) -> int:
        """Return the value reported by the sensor."""
        # Light level in 10000 log10 (lux) +1 measured by sensor. Logarithm
        # scale used because the human eye adjusts to light levels and small
        # changes at low lux levels are more noticeable than at high lux
        # levels.
        return int(10 ** ((self.resource.light.value - 1) / 10000))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the optional state attributes."""
        return {
            "light_level": self.resource.light.value,
        }


class HueBatterySensor(HueSensorBase):
    """Representation of a Hue Battery sensor."""

    entity_description = SensorEntityDescription(
        key="battery_sensor",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        has_entity_name=True,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    )

    @property
    def native_value(self) -> int:
        """Return the value reported by the sensor."""
        return self.resource.power_state.battery_level

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the optional state attributes."""
        if self.resource.power_state.battery_state is None:
            return {}
        return {"battery_state": self.resource.power_state.battery_state.value}


class HueZigbeeConnectivitySensor(HueSensorBase):
    """Representation of a Hue ZigbeeConnectivity sensor."""

    entity_description = SensorEntityDescription(
        key="zigbee_connectivity_sensor",
        device_class=SensorDeviceClass.ENUM,
        has_entity_name=True,
        entity_category=EntityCategory.DIAGNOSTIC,
        translation_key="zigbee_connectivity",
        options=[
            "connected",
            "disconnected",
            "connectivity_issue",
            "unidirectional_incoming",
        ],
        entity_registry_enabled_default=False,
    )

    @property
    def native_value(self) -> str:
        """Return the value reported by the sensor."""
        return self.resource.status.value

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the optional state attributes."""
        return {"mac_address": self.resource.mac_address}
