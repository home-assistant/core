"""The homee sensor platform."""

from collections.abc import Callable
from dataclasses import dataclass

from pyHomee.const import AttributeType, NodeState
from pyHomee.model import HomeeAttribute, HomeeNode

from homeassistant.components.automation import automations_with_entity
from homeassistant.components.script import scripts_with_entity
from homeassistant.components.sensor import (
    DOMAIN as SENSOR_DOMAIN,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.issue_registry import (
    IssueSeverity,
    async_create_issue,
    async_delete_issue,
)

from . import HomeeConfigEntry
from .const import (
    DOMAIN,
    HOMEE_UNIT_TO_HA_UNIT,
    OPEN_CLOSE_MAP,
    OPEN_CLOSE_MAP_REVERSED,
    WINDOW_MAP,
    WINDOW_MAP_REVERSED,
)
from .entity import HomeeEntity, HomeeNodeEntity
from .helpers import get_name_for_enum

PARALLEL_UPDATES = 0


def get_open_close_value(attribute: HomeeAttribute) -> str | None:
    """Return the open/close value."""
    vals = OPEN_CLOSE_MAP if not attribute.is_reversed else OPEN_CLOSE_MAP_REVERSED
    return vals.get(attribute.current_value)


def get_window_value(attribute: HomeeAttribute) -> str | None:
    """Return the states of a window open sensor."""
    vals = WINDOW_MAP if not attribute.is_reversed else WINDOW_MAP_REVERSED
    return vals.get(attribute.current_value)


def get_brightness_device_class(
    attribute: HomeeAttribute, device_class: SensorDeviceClass | None
) -> SensorDeviceClass | None:
    """Return the device class for a brightness sensor."""
    if attribute.unit == "%":
        return None
    return device_class


@dataclass(frozen=True, kw_only=True)
class HomeeSensorEntityDescription(SensorEntityDescription):
    """A class that describes Homee sensor entities."""

    device_class_fn: Callable[
        [HomeeAttribute, SensorDeviceClass | None], SensorDeviceClass | None
    ] = lambda attribute, device_class: device_class
    value_fn: Callable[[HomeeAttribute], str | float | None] = (
        lambda value: value.current_value
    )
    native_unit_of_measurement_fn: Callable[[str], str | None] = (
        lambda homee_unit: HOMEE_UNIT_TO_HA_UNIT[homee_unit]
    )


SENSOR_DESCRIPTIONS: dict[AttributeType, HomeeSensorEntityDescription] = {
    AttributeType.ACCUMULATED_ENERGY_USE: HomeeSensorEntityDescription(
        key="energy",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    AttributeType.BATTERY_LEVEL: HomeeSensorEntityDescription(
        key="battery",
        device_class=SensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    AttributeType.BRIGHTNESS: HomeeSensorEntityDescription(
        key="brightness",
        device_class=SensorDeviceClass.ILLUMINANCE,
        device_class_fn=get_brightness_device_class,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=(
            lambda attribute: attribute.current_value * 1000
            if attribute.unit == "klx"
            else attribute.current_value
        ),
    ),
    AttributeType.CURRENT: HomeeSensorEntityDescription(
        key="current",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    AttributeType.CURRENT_ENERGY_USE: HomeeSensorEntityDescription(
        key="power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    AttributeType.CURRENT_VALVE_POSITION: HomeeSensorEntityDescription(
        key="valve_position",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    AttributeType.DAWN: HomeeSensorEntityDescription(
        key="dawn",
        device_class=SensorDeviceClass.ILLUMINANCE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    AttributeType.DEVICE_TEMPERATURE: HomeeSensorEntityDescription(
        key="device_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    AttributeType.EXHAUST_MOTOR_REVS: HomeeSensorEntityDescription(
        key="exhaust_motor_revs",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    AttributeType.INDOOR_RELATIVE_HUMIDITY: HomeeSensorEntityDescription(
        key="indoor_humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    AttributeType.INDOOR_TEMPERATURE: HomeeSensorEntityDescription(
        key="indoor_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    AttributeType.INTAKE_MOTOR_REVS: HomeeSensorEntityDescription(
        key="intake_motor_revs",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    AttributeType.LEVEL: HomeeSensorEntityDescription(
        key="level",
        device_class=SensorDeviceClass.VOLUME_STORAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    AttributeType.LINK_QUALITY: HomeeSensorEntityDescription(
        key="link_quality",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    AttributeType.OPERATING_HOURS: HomeeSensorEntityDescription(
        key="operating_hours",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    AttributeType.OUTDOOR_RELATIVE_HUMIDITY: HomeeSensorEntityDescription(
        key="outdoor_humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    AttributeType.OUTDOOR_TEMPERATURE: HomeeSensorEntityDescription(
        key="outdoor_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    AttributeType.POSITION: HomeeSensorEntityDescription(
        key="position",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    AttributeType.RAIN_FALL_LAST_HOUR: HomeeSensorEntityDescription(
        key="rainfall_hour",
        device_class=SensorDeviceClass.PRECIPITATION,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    AttributeType.RAIN_FALL_TODAY: HomeeSensorEntityDescription(
        key="rainfall_day",
        device_class=SensorDeviceClass.PRECIPITATION,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    AttributeType.RELATIVE_HUMIDITY: HomeeSensorEntityDescription(
        key="humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    AttributeType.TEMPERATURE: HomeeSensorEntityDescription(
        key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    AttributeType.TOTAL_ACCUMULATED_ENERGY_USE: HomeeSensorEntityDescription(
        key="total_energy",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    AttributeType.TOTAL_CURRENT: HomeeSensorEntityDescription(
        key="total_current",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    AttributeType.TOTAL_CURRENT_ENERGY_USE: HomeeSensorEntityDescription(
        key="total_power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    AttributeType.TOTAL_VOLTAGE: HomeeSensorEntityDescription(
        key="total_voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    AttributeType.UP_DOWN: HomeeSensorEntityDescription(
        key="up_down",
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
        key="uv",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    AttributeType.VOLTAGE: HomeeSensorEntityDescription(
        key="voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    AttributeType.WIND_SPEED: HomeeSensorEntityDescription(
        key="wind_speed",
        device_class=SensorDeviceClass.WIND_SPEED,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    AttributeType.WINDOW_POSITION: HomeeSensorEntityDescription(
        key="window_position",
        device_class=SensorDeviceClass.ENUM,
        options=["closed", "open", "tilted"],
        value_fn=get_window_value,
    ),
}


@dataclass(frozen=True, kw_only=True)
class HomeeNodeSensorEntityDescription(SensorEntityDescription):
    """Describes Homee node sensor entities."""

    value_fn: Callable[[HomeeNode], str | None]


NODE_SENSOR_DESCRIPTIONS: tuple[HomeeNodeSensorEntityDescription, ...] = (
    HomeeNodeSensorEntityDescription(
        key="state",
        device_class=SensorDeviceClass.ENUM,
        options=[
            "available",
            "unavailable",
            "update_in_progress",
            "waiting_for_attributes",
            "initializing",
            "user_interaction_required",
            "password_required",
            "host_unavailable",
            "delete_in_progress",
            "cosi_connected",
            "blocked",
            "waiting_for_wakeup",
            "remote_node_deleted",
            "firmware_update_in_progress",
        ],
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        translation_key="node_state",
        value_fn=lambda node: get_name_for_enum(NodeState, node.state),
    ),
)


def entity_used_in(hass: HomeAssistant, entity_id: str) -> list[str]:
    """Get list of related automations and scripts."""
    used_in = automations_with_entity(hass, entity_id)
    used_in += scripts_with_entity(hass, entity_id)
    return used_in


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: HomeeConfigEntry,
    async_add_devices: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the homee platform for the sensor components."""
    ent_reg = er.async_get(hass)
    devices: list[HomeeSensor | HomeeNodeSensor] = []

    def add_deprecated_entity(
        attribute: HomeeAttribute, description: HomeeSensorEntityDescription
    ) -> None:
        """Add deprecated entities."""
        entity_uid = f"{config_entry.runtime_data.settings.uid}-{attribute.node_id}-{attribute.id}"
        if entity_id := ent_reg.async_get_entity_id(SENSOR_DOMAIN, DOMAIN, entity_uid):
            entity_entry = ent_reg.async_get(entity_id)
            if entity_entry and entity_entry.disabled:
                ent_reg.async_remove(entity_id)
                async_delete_issue(
                    hass,
                    DOMAIN,
                    f"deprecated_entity_{entity_uid}",
                )
            elif entity_entry:
                devices.append(HomeeSensor(attribute, config_entry, description))
                if entity_used_in(hass, entity_id):
                    async_create_issue(
                        hass,
                        DOMAIN,
                        f"deprecated_entity_{entity_uid}",
                        breaks_in_ha_version="2025.12.0",
                        is_fixable=False,
                        severity=IssueSeverity.WARNING,
                        translation_key="deprecated_entity",
                        translation_placeholders={
                            "name": str(
                                entity_entry.name or entity_entry.original_name
                            ),
                            "entity": entity_id,
                        },
                    )

    for node in config_entry.runtime_data.nodes:
        # Node properties that are sensors.
        devices.extend(
            HomeeNodeSensor(node, config_entry, description)
            for description in NODE_SENSOR_DESCRIPTIONS
        )

        # Node attributes that are sensors.
        for attribute in node.attributes:
            if attribute.type == AttributeType.CURRENT_VALVE_POSITION:
                add_deprecated_entity(attribute, SENSOR_DESCRIPTIONS[attribute.type])
            elif attribute.type in SENSOR_DESCRIPTIONS and not attribute.editable:
                devices.append(
                    HomeeSensor(
                        attribute, config_entry, SENSOR_DESCRIPTIONS[attribute.type]
                    )
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
        self._attr_translation_key = description.key
        if attribute.instance > 0:
            self._attr_translation_key = f"{self._attr_translation_key}_instance"
            self._attr_translation_placeholders = {"instance": str(attribute.instance)}
        self._attr_device_class = description.device_class_fn(
            attribute, description.device_class
        )

    @property
    def native_value(self) -> float | str | None:
        """Return the native value of the sensor."""
        return self.entity_description.value_fn(self._attribute)

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the native unit of the sensor."""
        return self.entity_description.native_unit_of_measurement_fn(
            self._attribute.unit
        )


class HomeeNodeSensor(HomeeNodeEntity, SensorEntity):
    """Represents a sensor based on a node's property."""

    entity_description: HomeeNodeSensorEntityDescription

    def __init__(
        self,
        node: HomeeNode,
        entry: HomeeConfigEntry,
        description: HomeeNodeSensorEntityDescription,
    ) -> None:
        """Initialize a homee node sensor entity."""
        super().__init__(node, entry)
        self.entity_description = description
        self._node = node
        self._attr_unique_id = f"{self._attr_unique_id}-{description.key}"

    @property
    def native_value(self) -> str | None:
        """Return the sensors value."""
        return self.entity_description.value_fn(self._node)
