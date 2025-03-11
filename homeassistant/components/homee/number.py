"""The Homee number platform."""

from pyHomee.const import AttributeType
from pyHomee.model import HomeeAttribute

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import HomeeConfigEntry
from .const import HOMEE_UNIT_TO_HA_UNIT
from .entity import HomeeEntity

PARALLEL_UPDATES = 0

NUMBER_DESCRIPTIONS = {
    AttributeType.DOWN_POSITION: NumberEntityDescription(
        key="down_position",
        entity_category=EntityCategory.CONFIG,
    ),
    AttributeType.DOWN_SLAT_POSITION: NumberEntityDescription(
        key="down_slat_position",
        entity_category=EntityCategory.CONFIG,
    ),
    AttributeType.DOWN_TIME: NumberEntityDescription(
        key="down_time",
        device_class=NumberDeviceClass.DURATION,
        entity_category=EntityCategory.CONFIG,
    ),
    AttributeType.ENDPOSITION_CONFIGURATION: NumberEntityDescription(
        key="endposition_configuration",
        entity_category=EntityCategory.CONFIG,
    ),
    AttributeType.MOTION_ALARM_CANCELATION_DELAY: NumberEntityDescription(
        key="motion_alarm_cancelation_delay",
        device_class=NumberDeviceClass.DURATION,
        entity_category=EntityCategory.CONFIG,
    ),
    AttributeType.OPEN_WINDOW_DETECTION_SENSIBILITY: NumberEntityDescription(
        key="open_window_detection_sensibility",
        entity_category=EntityCategory.CONFIG,
    ),
    AttributeType.POLLING_INTERVAL: NumberEntityDescription(
        key="polling_interval",
        device_class=NumberDeviceClass.DURATION,
        entity_category=EntityCategory.CONFIG,
    ),
    AttributeType.SHUTTER_SLAT_TIME: NumberEntityDescription(
        key="shutter_slat_time",
        device_class=NumberDeviceClass.DURATION,
        entity_category=EntityCategory.CONFIG,
    ),
    AttributeType.SLAT_MAX_ANGLE: NumberEntityDescription(
        key="slat_max_angle",
        entity_category=EntityCategory.CONFIG,
    ),
    AttributeType.SLAT_MIN_ANGLE: NumberEntityDescription(
        key="slat_min_angle",
        entity_category=EntityCategory.CONFIG,
    ),
    AttributeType.SLAT_STEPS: NumberEntityDescription(
        key="slat_steps",
        entity_category=EntityCategory.CONFIG,
    ),
    AttributeType.TEMPERATURE_OFFSET: NumberEntityDescription(
        key="temperature_offset",
        entity_category=EntityCategory.CONFIG,
    ),
    AttributeType.UP_TIME: NumberEntityDescription(
        key="up_time",
        device_class=NumberDeviceClass.DURATION,
        entity_category=EntityCategory.CONFIG,
    ),
    AttributeType.WAKE_UP_INTERVAL: NumberEntityDescription(
        key="wake_up_interval",
        device_class=NumberDeviceClass.DURATION,
        entity_category=EntityCategory.CONFIG,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: HomeeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the Homee platform for the number component."""

    async_add_entities(
        HomeeNumber(attribute, config_entry, NUMBER_DESCRIPTIONS[attribute.type])
        for node in config_entry.runtime_data.nodes
        for attribute in node.attributes
        if attribute.type in NUMBER_DESCRIPTIONS and attribute.data != "fixed_value"
    )


class HomeeNumber(HomeeEntity, NumberEntity):
    """Representation of a Homee number."""

    def __init__(
        self,
        attribute: HomeeAttribute,
        entry: HomeeConfigEntry,
        description: NumberEntityDescription,
    ) -> None:
        """Initialize a Homee number entity."""
        super().__init__(attribute, entry)
        self.entity_description = description
        self._attr_translation_key = description.key
        self._attr_native_unit_of_measurement = HOMEE_UNIT_TO_HA_UNIT[attribute.unit]
        self._attr_native_min_value = attribute.minimum
        self._attr_native_max_value = attribute.maximum
        self._attr_native_step = attribute.step_value

    @property
    def available(self) -> bool:
        """Return the availability of the entity."""
        return super().available and self._attribute.editable

    @property
    def native_value(self) -> int:
        """Return the native value of the number."""
        return int(self._attribute.current_value)

    async def async_set_native_value(self, value: float) -> None:
        """Set the selected value."""
        await self.async_set_homee_value(value)
