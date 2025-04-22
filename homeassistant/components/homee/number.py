"""The Homee number platform."""

from collections.abc import Callable
from dataclasses import dataclass

from pyHomee.const import AttributeType
from pyHomee.model import HomeeAttribute

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
)
from homeassistant.const import EntityCategory, UnitOfSpeed
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import HomeeConfigEntry
from .const import HOMEE_UNIT_TO_HA_UNIT
from .entity import HomeeEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class HomeeNumberEntityDescription(NumberEntityDescription):
    """A class that describes Homee number entities."""

    native_value_fn: Callable[[float], float] = lambda value: value
    set_native_value_fn: Callable[[float], float] = lambda value: value


NUMBER_DESCRIPTIONS = {
    AttributeType.DOWN_POSITION: HomeeNumberEntityDescription(
        key="down_position",
        entity_category=EntityCategory.CONFIG,
    ),
    AttributeType.DOWN_SLAT_POSITION: HomeeNumberEntityDescription(
        key="down_slat_position",
        entity_category=EntityCategory.CONFIG,
    ),
    AttributeType.DOWN_TIME: HomeeNumberEntityDescription(
        key="down_time",
        device_class=NumberDeviceClass.DURATION,
        entity_category=EntityCategory.CONFIG,
    ),
    AttributeType.ENDPOSITION_CONFIGURATION: HomeeNumberEntityDescription(
        key="endposition_configuration",
        entity_category=EntityCategory.CONFIG,
    ),
    AttributeType.MOTION_ALARM_CANCELATION_DELAY: HomeeNumberEntityDescription(
        key="motion_alarm_cancelation_delay",
        device_class=NumberDeviceClass.DURATION,
        entity_category=EntityCategory.CONFIG,
    ),
    AttributeType.OPEN_WINDOW_DETECTION_SENSIBILITY: HomeeNumberEntityDescription(
        key="open_window_detection_sensibility",
        entity_category=EntityCategory.CONFIG,
    ),
    AttributeType.POLLING_INTERVAL: HomeeNumberEntityDescription(
        key="polling_interval",
        device_class=NumberDeviceClass.DURATION,
        entity_category=EntityCategory.CONFIG,
    ),
    AttributeType.SHUTTER_SLAT_TIME: HomeeNumberEntityDescription(
        key="shutter_slat_time",
        device_class=NumberDeviceClass.DURATION,
        entity_category=EntityCategory.CONFIG,
    ),
    AttributeType.SLAT_MAX_ANGLE: HomeeNumberEntityDescription(
        key="slat_max_angle",
        entity_category=EntityCategory.CONFIG,
    ),
    AttributeType.SLAT_MIN_ANGLE: HomeeNumberEntityDescription(
        key="slat_min_angle",
        entity_category=EntityCategory.CONFIG,
    ),
    AttributeType.SLAT_STEPS: HomeeNumberEntityDescription(
        key="slat_steps",
        entity_category=EntityCategory.CONFIG,
    ),
    AttributeType.TEMPERATURE_OFFSET: HomeeNumberEntityDescription(
        key="temperature_offset",
        entity_category=EntityCategory.CONFIG,
    ),
    AttributeType.UP_TIME: HomeeNumberEntityDescription(
        key="up_time",
        device_class=NumberDeviceClass.DURATION,
        entity_category=EntityCategory.CONFIG,
    ),
    AttributeType.WAKE_UP_INTERVAL: HomeeNumberEntityDescription(
        key="wake_up_interval",
        device_class=NumberDeviceClass.DURATION,
        entity_category=EntityCategory.CONFIG,
    ),
    AttributeType.WIND_MONITORING_STATE: HomeeNumberEntityDescription(
        key="wind_monitoring_state",
        device_class=NumberDeviceClass.WIND_SPEED,
        entity_category=EntityCategory.CONFIG,
        native_min_value=0,
        native_max_value=22.5,
        native_step=2.5,
        native_unit_of_measurement=UnitOfSpeed.METERS_PER_SECOND,
        native_value_fn=lambda value: value * 2.5,
        set_native_value_fn=lambda value: value / 2.5,
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

    entity_description: HomeeNumberEntityDescription

    def __init__(
        self,
        attribute: HomeeAttribute,
        entry: HomeeConfigEntry,
        description: HomeeNumberEntityDescription,
    ) -> None:
        """Initialize a Homee number entity."""
        super().__init__(attribute, entry)
        self.entity_description = description
        self._attr_translation_key = description.key
        self._attr_native_unit_of_measurement = (
            description.native_unit_of_measurement
            or HOMEE_UNIT_TO_HA_UNIT[attribute.unit]
        )
        self._attr_native_min_value = description.native_min_value or attribute.minimum
        self._attr_native_max_value = description.native_max_value or attribute.maximum
        self._attr_native_step = description.native_step or attribute.step_value

    @property
    def available(self) -> bool:
        """Return the availability of the entity."""
        return super().available and self._attribute.editable

    @property
    def native_value(self) -> float | None:
        """Return the native value of the number."""
        return self.entity_description.native_value_fn(self._attribute.current_value)

    async def async_set_native_value(self, value: float) -> None:
        """Set the selected value."""
        await self.async_set_homee_value(
            self.entity_description.set_native_value_fn(value)
        )
