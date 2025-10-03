"""Support for Hue sensors."""

from __future__ import annotations

from functools import partial
from typing import Any

from aiohue.v2 import HueBridgeV2
from aiohue.v2.controllers.events import EventType
from aiohue.v2.controllers.sensors import (
    DevicePowerController,
    GroupedLightLevelController,
    LightLevelController,
    SensorsController,
    TemperatureController,
    ZigbeeConnectivityController,
)
from aiohue.v2.models.device_power import DevicePower
from aiohue.v2.models.grouped_light_level import GroupedLightLevel
from aiohue.v2.models.light_level import LightLevel
from aiohue.v2.models.resource import ResourceTypes
from aiohue.v2.models.temperature import Temperature
from aiohue.v2.models.zigbee_connectivity import ZigbeeConnectivity

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import LIGHT_LUX, PERCENTAGE, EntityCategory, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from ..bridge import HueBridge, HueConfigEntry
from ..const import DOMAIN
from .entity import HueBaseEntity

type SensorType = (
    DevicePower | LightLevel | Temperature | ZigbeeConnectivity | GroupedLightLevel
)
type ControllerType = (
    DevicePowerController
    | LightLevelController
    | TemperatureController
    | ZigbeeConnectivityController
    | GroupedLightLevelController
)


def _resource_valid(
    resource: SensorType, controller: ControllerType, api: HueBridgeV2
) -> bool:
    """Return True if the resource is valid."""
    if isinstance(resource, GroupedLightLevel):
        # filter out GroupedLightLevel sensors that are not linked to a valid group/parent
        if resource.owner.rtype not in (
            ResourceTypes.ROOM,
            ResourceTypes.ZONE,
            ResourceTypes.SERVICE_GROUP,
        ):
            return False
        # guard against GroupedLightLevel without parent (should not happen, but just in case)
        parent_id = resource.owner.rid
        parent = api.groups.get(parent_id) or api.config.get(parent_id)
        if not parent:
            return False
        # filter out GroupedLightLevel sensors that have only one member, because Hue creates one
        # default grouped LightLevel sensor per zone/room, which is not useful to expose in HA
        if len(parent.children) <= 1:
            return False
    # default/other checks can go here (none for now)
    return True


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: HueConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Hue Sensors from Config Entry."""
    bridge = config_entry.runtime_data
    api: HueBridgeV2 = bridge.api
    ctrl_base: SensorsController = api.sensors

    @callback
    def register_items(controller: ControllerType, sensor_class: SensorType):
        make_sensor_entity = partial(sensor_class, bridge, controller)

        @callback
        def async_add_sensor(event_type: EventType, resource: SensorType) -> None:
            """Add Hue Sensor."""
            if not _resource_valid(resource, controller, api):
                return
            async_add_entities([make_sensor_entity(resource)])

        # add all current items in controller
        async_add_entities(
            make_sensor_entity(sensor)
            for sensor in controller
            if _resource_valid(sensor, controller, api)
        )

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
    register_items(api.sensors.grouped_light_level, HueGroupedLightLevelSensor)


# pylint: disable-next=hass-enforce-class-module
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


# pylint: disable-next=hass-enforce-class-module
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


# pylint: disable-next=hass-enforce-class-module
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


# pylint: disable-next=hass-enforce-class-module
class HueGroupedLightLevelSensor(HueLightLevelSensor):
    """Representation of a LightLevel (illuminance) sensor from a Hue GroupedLightLevel resource."""

    controller: GroupedLightLevelController
    resource: GroupedLightLevel

    def __init__(
        self,
        bridge: HueBridge,
        controller: GroupedLightLevelController,
        resource: GroupedLightLevel,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(bridge, controller, resource)
        # link the GroupedLightLevel sensor to the parent the sensor is associated with
        # which can either be a special ServiceGroup or a Zone/Room
        api = self.bridge.api
        parent_id = resource.owner.rid
        parent = api.groups.get(parent_id) or api.config.get(parent_id)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, parent.id)},
        )


# pylint: disable-next=hass-enforce-class-module
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


# pylint: disable-next=hass-enforce-class-module
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
