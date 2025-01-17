"""The homee sensor platform."""

from collections.abc import Callable
from dataclasses import dataclass

from pyHomee.const import AttributeType, NodeProtocol, NodeState
from pyHomee.model import HomeeAttribute, HomeeNode

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HomeeConfigEntry, helpers
from .const import OPEN_CLOSE_MAP, OPEN_CLOSE_MAP_REVERSED
from .entity import HomeeEntity, HomeeNodeEntity


def get_open_close_value(attribute: HomeeAttribute) -> str | None:
    """Return the open/close value."""
    vals = OPEN_CLOSE_MAP if not attribute.is_reversed else OPEN_CLOSE_MAP_REVERSED
    return vals.get(attribute.current_value)


@dataclass(frozen=True, kw_only=True)
class HomeeSensorEntityDescription(SensorEntityDescription):
    """A class that describes Homee sensor entities."""

    value_fn: Callable[[HomeeAttribute], str | float | None] = (
        lambda value: value.current_value
    )


SENSOR_DESCRIPTIONS: dict[AttributeType, HomeeSensorEntityDescription] = {
    AttributeType.ACCUMULATED_ENERGY_USE: HomeeSensorEntityDescription(
        key=AttributeType.ACCUMULATED_ENERGY_USE,
        translation_key="energy_sensor",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    AttributeType.BATTERY_LEVEL: HomeeSensorEntityDescription(
        key=AttributeType.BATTERY_LEVEL,
        translation_key="battery_sensor",
        device_class=SensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    AttributeType.BRIGHTNESS: HomeeSensorEntityDescription(
        key=AttributeType.BRIGHTNESS,
        translation_key="brightness_sensor",
        device_class=SensorDeviceClass.ILLUMINANCE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    AttributeType.BUTTON_STATE: HomeeSensorEntityDescription(
        key=AttributeType.BUTTON_STATE,
        translation_key="button_state_sensor",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    AttributeType.CURRENT: HomeeSensorEntityDescription(
        key=AttributeType.CURRENT,
        translation_key="current_sensor",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    AttributeType.CURRENT_ENERGY_USE: HomeeSensorEntityDescription(
        key=AttributeType.CURRENT_ENERGY_USE,
        translation_key="power_sensor",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    AttributeType.CURRENT_VALVE_POSITION: HomeeSensorEntityDescription(
        key=AttributeType.CURRENT_VALVE_POSITION,
        translation_key="valve_position_sensor",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    AttributeType.DAWN: HomeeSensorEntityDescription(
        key=AttributeType.DAWN,
        translation_key="dawn_sensor",
        device_class=SensorDeviceClass.ILLUMINANCE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    AttributeType.DEVICE_TEMPERATURE: HomeeSensorEntityDescription(
        key=AttributeType.DEVICE_TEMPERATURE,
        translation_key="device_temperature_sensor",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    AttributeType.LINK_QUALITY: HomeeSensorEntityDescription(
        key=AttributeType.LINK_QUALITY,
        translation_key="link_quality_sensor",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    AttributeType.POSITION: HomeeSensorEntityDescription(
        key=AttributeType.POSITION,
        translation_key="position_sensor",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    AttributeType.RAIN_FALL_LAST_HOUR: HomeeSensorEntityDescription(
        key=AttributeType.RAIN_FALL_LAST_HOUR,
        translation_key="rainfall_hour_sensor",
        device_class=SensorDeviceClass.PRECIPITATION,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    AttributeType.RAIN_FALL_TODAY: HomeeSensorEntityDescription(
        key=AttributeType.RAIN_FALL_TODAY,
        translation_key="rainfall_day_sensor",
        device_class=SensorDeviceClass.PRECIPITATION,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    AttributeType.RELATIVE_HUMIDITY: HomeeSensorEntityDescription(
        key=AttributeType.RELATIVE_HUMIDITY,
        translation_key="relative_humidity_sensor",
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    AttributeType.TEMPERATURE: HomeeSensorEntityDescription(
        key=AttributeType.TEMPERATURE,
        translation_key="temperature_sensor",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    AttributeType.TOTAL_ACCUMULATED_ENERGY_USE: HomeeSensorEntityDescription(
        key=AttributeType.TOTAL_ACCUMULATED_ENERGY_USE,
        translation_key="total_energy_sensor",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    AttributeType.TOTAL_CURRENT: HomeeSensorEntityDescription(
        key=AttributeType.TOTAL_CURRENT,
        translation_key="total_current_sensor",
        device_class=SensorDeviceClass.CURRENT,
    ),
    AttributeType.TOTAL_CURRENT_ENERGY_USE: HomeeSensorEntityDescription(
        key=AttributeType.TOTAL_CURRENT_ENERGY_USE,
        translation_key="total_power_sensor",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    AttributeType.TOTAL_VOLTAGE: HomeeSensorEntityDescription(
        key=AttributeType.TOTAL_VOLTAGE,
        translation_key="total_voltage_sensor",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    AttributeType.UP_DOWN: HomeeSensorEntityDescription(
        key=AttributeType.UP_DOWN,
        translation_key="up_down_sensor",
        device_class=SensorDeviceClass.ENUM,
        options=[
            "open",
            "closed",
            "partial",
            "opening",
            "closing",
        ],
        value_fn=get_open_close_value,
    ),
    AttributeType.UV: HomeeSensorEntityDescription(
        key=AttributeType.UV,
        translation_key="uv_sensor",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    AttributeType.VOLTAGE: HomeeSensorEntityDescription(
        key=AttributeType.VOLTAGE,
        translation_key="voltage_sensor",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    AttributeType.WIND_SPEED: HomeeSensorEntityDescription(
        key=AttributeType.WIND_SPEED,
        translation_key="wind_speed_sensor",
        device_class=SensorDeviceClass.WIND_SPEED,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    AttributeType.WINDOW_POSITION: HomeeSensorEntityDescription(
        key=AttributeType.WINDOW_POSITION,
        translation_key="window_position_sensor",
        device_class=SensorDeviceClass.ENUM,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: HomeeConfigEntry,
    async_add_devices: AddEntitiesCallback,
) -> None:
    """Add the homee platform for the sensor components."""

    devices: list[HomeeSensor | HomeeNodeSensor] = []
    for node in config_entry.runtime_data.nodes:
        # Node properties that are sensors.
        props = ["state", "protocol"]
        devices.extend(HomeeNodeSensor(node, config_entry, item) for item in props)

        # Node attributes that are sensors.
        devices.extend(
            HomeeSensor(attribute, config_entry, SENSOR_DESCRIPTIONS[attribute.type])
            for attribute in node.attributes
            if attribute.type in SENSOR_DESCRIPTIONS and not attribute.editable
        )

    if devices:
        async_add_devices(devices)


class HomeeSensor(HomeeEntity, SensorEntity):
    """Representation of a homee sensor."""

    entity_description: HomeeSensorEntityDescription

    def __init__(
        self,
        attribute: HomeeAttribute,
        entry: HomeeConfigEntry,
        description: HomeeSensorEntityDescription,
    ) -> None:
        """Initialize a homee sensor entity."""
        super().__init__(attribute, entry)
        self.entity_description = description
        if attribute.instance > 0:
            self._attr_translation_key = f"{description.translation_key}_instance"
        self._attr_translation_placeholders = {"instance": str(attribute.instance)}

    @property
    def native_value(self) -> float | str | None:
        """Return the native value of the sensor."""
        return self.entity_description.value_fn(self._attribute)

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the native unit of the sensor."""
        if self._attribute.unit == "n/a":
            return None
        if self.translation_key == "uv_sensor":
            return "UV Index"

        if self._attribute.unit == "klx":
            return "lx"

        return self._attribute.unit


class HomeeNodeSensor(HomeeNodeEntity, SensorEntity):
    """Represents a sensor based on a node's property."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False

    def __init__(
        self,
        node: HomeeNode,
        entry: HomeeConfigEntry,
        prop_name: str,
    ) -> None:
        """Initialize a homee node sensor entity."""
        super().__init__(node, entry)
        self._node = node
        self._attr_unique_id = f"{self._attr_unique_id}-{prop_name}"
        self._prop_name = prop_name
        self._attr_translation_key = f"node_sensor_{prop_name}"

    @property
    def native_value(self) -> str:
        """Return the sensors value."""
        value = getattr(self._node, self._prop_name)
        att_class = {"state": NodeState, "protocol": NodeProtocol}

        state = helpers.get_name_for_enum(att_class[self._prop_name], value)
        return state.lower()
