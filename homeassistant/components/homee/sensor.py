"""The homee sensor platform."""

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
from .entity import HomeeEntity, HomeeNodeEntity

SENSOR_DESCRIPTIONS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key=AttributeType.BATTERY_LEVEL,
        translation_key="battery_sensor",
        device_class=SensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=AttributeType.BRIGHTNESS,
        translation_key="brightness_sensor",
        device_class=SensorDeviceClass.ILLUMINANCE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=AttributeType.BUTTON_STATE,
        translation_key="button_state_sensor",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=AttributeType.CURRENT,
        translation_key="current_sensor",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=AttributeType.TOTAL_CURRENT,
        translation_key="total_current_sensor",
        device_class=SensorDeviceClass.CURRENT,
    ),
    SensorEntityDescription(
        key=AttributeType.CURRENT_VALVE_POSITION,
        translation_key="valve_position_sensor",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=AttributeType.DAWN,
        translation_key="dawn_sensor",
        device_class=SensorDeviceClass.ILLUMINANCE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=AttributeType.ACCUMULATED_ENERGY_USE,
        translation_key="energy_sensor",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key=AttributeType.TOTAL_ACCUMULATED_ENERGY_USE,
        translation_key="total_energy_sensor",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key=AttributeType.RELATIVE_HUMIDITY,
        translation_key="relative_humidity_sensor",
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=AttributeType.LINK_QUALITY,
        translation_key="link_quality_sensor",
        icon="mdi:signal",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=AttributeType.POSITION,
        translation_key="position_sensor",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=AttributeType.CURRENT_ENERGY_USE,
        translation_key="power_sensor",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=AttributeType.TOTAL_CURRENT_ENERGY_USE,
        translation_key="total_power_sensor",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=AttributeType.RAIN_FALL_LAST_HOUR,
        translation_key="rainfall_hour_sensor",
        device_class=SensorDeviceClass.PRECIPITATION,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=AttributeType.RAIN_FALL_TODAY,
        translation_key="rainfall_day_sensor",
        device_class=SensorDeviceClass.PRECIPITATION,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=AttributeType.TEMPERATURE,
        translation_key="temperature_sensor",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=AttributeType.DEVICE_TEMPERATURE,
        translation_key="device_temperature_sensor",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=AttributeType.UP_DOWN,
        translation_key="up_down_sensor",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=AttributeType.UV,
        translation_key="uv_sensor",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=AttributeType.VOLTAGE,
        translation_key="voltage_sensor",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=AttributeType.TOTAL_VOLTAGE,
        translation_key="total_voltage_sensor",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=AttributeType.WIND_SPEED,
        translation_key="wind_speed_sensor",
        device_class=SensorDeviceClass.WIND_SPEED,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=AttributeType.WINDOW_POSITION,
        translation_key="window_position_sensor",
        icon="mdi:window-closed",
        state_class=SensorStateClass.MEASUREMENT,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: HomeeConfigEntry,
    async_add_devices: AddEntitiesCallback,
) -> None:
    """Add the homee platform for the sensor components."""

    devices: list[HomeeSensor | HomeeNodeSensor] = []
    for node in config_entry.runtime_data.nodes:
        props = ["state", "protocol"]
        devices.extend(HomeeNodeSensor(node, config_entry, item) for item in props)

        for attribute in node.attributes:
            devices.extend(
                HomeeSensor(attribute, config_entry, sensor_descr)
                for sensor_descr in SENSOR_DESCRIPTIONS
                if attribute.type == sensor_descr.key
            )

    if devices:
        async_add_devices(devices)


class HomeeSensor(HomeeEntity, SensorEntity):
    """Representation of a homee sensor."""

    def __init__(
        self,
        attribute: HomeeAttribute,
        entry: HomeeConfigEntry,
        sensor_descr: SensorEntityDescription,
    ) -> None:
        """Initialize a homee sensor entity."""
        super().__init__(attribute, entry)
        self.entity_description = sensor_descr
        self._attribute = attribute
        self._sensor_index = attribute.instance

        self._attr_unique_id = (
            f"{entry.runtime_data.settings.uid}-{attribute.node_id}-{attribute.id}"
        )

    @property
    def translation_key(self) -> str | None:
        """Return the translation key of the sensor entity."""
        trans_key = self.entity_description.translation_key

        if self._attribute.instance > 0:
            trans_key = f"{trans_key}_{self._attribute.instance}"
        if self._attribute.is_reversed:
            trans_key = f"{trans_key}_rev"

        return trans_key

    @property
    def native_value(self) -> int:
        """Return the native value of the sensor."""
        if self._attribute.type in [
            AttributeType.UP_DOWN,
            AttributeType.WINDOW_POSITION,
        ]:
            return int(self._attribute.current_value)

        if self._attribute.unit == "klx":
            return self._attribute.current_value * 1000

        return self._attribute.current_value

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
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_entity_registry_enabled_default = False
        self._attr_translation_key = f"node_sensor_{prop_name}"

    @property
    def native_value(self) -> str:
        """Return the sensors value."""
        value = getattr(self._node, self._prop_name)
        att_class = {"state": NodeState, "protocol": NodeProtocol}

        state = helpers.get_name_for_enum(att_class[self._prop_name], value)
        return state.lower()
