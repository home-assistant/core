"""The Homee binary sensor platform."""

from pyHomee.const import AttributeType
from pyHomee.model import HomeeAttribute

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import HomeeConfigEntry
from .entity import HomeeEntity

PARALLEL_UPDATES = 0

BINARY_SENSOR_DESCRIPTIONS: dict[AttributeType, BinarySensorEntityDescription] = {
    AttributeType.BATTERY_LOW_ALARM: BinarySensorEntityDescription(
        key="battery",
        device_class=BinarySensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    AttributeType.BLACKOUT_ALARM: BinarySensorEntityDescription(
        key="blackout_alarm",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    AttributeType.COALARM: BinarySensorEntityDescription(
        key="carbon_monoxide", device_class=BinarySensorDeviceClass.CO
    ),
    AttributeType.CO2ALARM: BinarySensorEntityDescription(
        key="carbon_dioxide", device_class=BinarySensorDeviceClass.PROBLEM
    ),
    AttributeType.FLOOD_ALARM: BinarySensorEntityDescription(
        key="flood",
        device_class=BinarySensorDeviceClass.MOISTURE,
    ),
    AttributeType.HIGH_TEMPERATURE_ALARM: BinarySensorEntityDescription(
        key="high_temperature",
        device_class=BinarySensorDeviceClass.HEAT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    AttributeType.LEAK_ALARM: BinarySensorEntityDescription(
        key="leak_alarm",
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    AttributeType.LOAD_ALARM: BinarySensorEntityDescription(
        key="load_alarm",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    AttributeType.LOCK_STATE: BinarySensorEntityDescription(
        key="lock",
        device_class=BinarySensorDeviceClass.LOCK,
    ),
    AttributeType.LOW_TEMPERATURE_ALARM: BinarySensorEntityDescription(
        key="low_temperature",
        device_class=BinarySensorDeviceClass.COLD,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    AttributeType.MALFUNCTION_ALARM: BinarySensorEntityDescription(
        key="malfunction",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    AttributeType.MAXIMUM_ALARM: BinarySensorEntityDescription(
        key="maximum",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    AttributeType.MINIMUM_ALARM: BinarySensorEntityDescription(
        key="minimum",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    AttributeType.MOTION_ALARM: BinarySensorEntityDescription(
        key="motion",
        device_class=BinarySensorDeviceClass.MOTION,
    ),
    AttributeType.MOTOR_BLOCKED_ALARM: BinarySensorEntityDescription(
        key="motor_blocked",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    AttributeType.ON_OFF: BinarySensorEntityDescription(
        key="plug",
        device_class=BinarySensorDeviceClass.PLUG,
    ),
    AttributeType.OPEN_CLOSE: BinarySensorEntityDescription(
        key="opening",
        device_class=BinarySensorDeviceClass.OPENING,
    ),
    AttributeType.OVER_CURRENT_ALARM: BinarySensorEntityDescription(
        key="overcurrent",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    AttributeType.OVERLOAD_ALARM: BinarySensorEntityDescription(
        key="overload",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    AttributeType.PRESENCE_ALARM: BinarySensorEntityDescription(
        key="presence",
        device_class=BinarySensorDeviceClass.PRESENCE,
    ),
    AttributeType.POWER_SUPPLY_ALARM: BinarySensorEntityDescription(
        key="power",
        device_class=BinarySensorDeviceClass.POWER,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    AttributeType.RAIN_FALL: BinarySensorEntityDescription(
        key="rain",
        device_class=BinarySensorDeviceClass.MOISTURE,
    ),
    AttributeType.REPLACE_FILTER_ALARM: BinarySensorEntityDescription(
        key="replace_filter",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    AttributeType.SMOKE_ALARM: BinarySensorEntityDescription(
        key="smoke",
        device_class=BinarySensorDeviceClass.SMOKE,
    ),
    AttributeType.STORAGE_ALARM: BinarySensorEntityDescription(
        key="storage",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    AttributeType.SURGE_ALARM: BinarySensorEntityDescription(
        key="surge",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    AttributeType.TAMPER_ALARM: BinarySensorEntityDescription(
        key="tamper",
        device_class=BinarySensorDeviceClass.TAMPER,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    AttributeType.VOLTAGE_DROP_ALARM: BinarySensorEntityDescription(
        key="voltage_drop",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    AttributeType.WATER_ALARM: BinarySensorEntityDescription(
        key="water",
        device_class=BinarySensorDeviceClass.MOISTURE,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: HomeeConfigEntry,
    async_add_devices: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the Homee platform for the binary sensor component."""

    async_add_devices(
        HomeeBinarySensor(
            attribute, config_entry, BINARY_SENSOR_DESCRIPTIONS[attribute.type]
        )
        for node in config_entry.runtime_data.nodes
        for attribute in node.attributes
        if attribute.type in BINARY_SENSOR_DESCRIPTIONS and not attribute.editable
    )


class HomeeBinarySensor(HomeeEntity, BinarySensorEntity):
    """Representation of a Homee binary sensor."""

    def __init__(
        self,
        attribute: HomeeAttribute,
        entry: HomeeConfigEntry,
        description: BinarySensorEntityDescription,
    ) -> None:
        """Initialize a Homee binary sensor entity."""
        super().__init__(attribute, entry)

        self.entity_description = description
        self._attr_translation_key = description.key

    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        return bool(self._attribute.current_value)
