"""Support for the Swing2Sleep Smarla sensor entities."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from pysmarlaapi.federwiege.services.classes import Property
from pysmarlaapi.federwiege.services.types import SpringStatus

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
    StateType,
)
from homeassistant.const import UnitOfLength, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import FederwiegeConfigEntry
from .entity import SmarlaBaseEntity, SmarlaEntityDescription

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class SmarlaSensorEntityDescription(SmarlaEntityDescription, SensorEntityDescription):
    """Class describing Swing2Sleep Smarla sensor entities."""

    value_fn: Callable[[Any], StateType] = lambda value: value
    multiple: bool = False
    value_pos: int = 0


SENSORS: list[SmarlaSensorEntityDescription] = [
    SmarlaSensorEntityDescription(
        key="amplitude",
        translation_key="amplitude",
        service="analyser",
        property="oscillation",
        multiple=True,
        value_pos=0,
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.MILLIMETERS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SmarlaSensorEntityDescription(
        key="period",
        translation_key="period",
        service="analyser",
        property="oscillation",
        multiple=True,
        value_pos=1,
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MILLISECONDS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SmarlaSensorEntityDescription(
        key="activity",
        translation_key="activity",
        service="analyser",
        property="activity",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SmarlaSensorEntityDescription(
        key="swing_count",
        translation_key="swing_count",
        service="analyser",
        property="swing_count",
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SmarlaSensorEntityDescription(
        key="total_swing_time",
        translation_key="total_swing_time",
        service="info",
        property="total_swing_time",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_unit_of_measurement=UnitOfTime.HOURS,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SmarlaSensorEntityDescription(
        key="spring_status",
        translation_key="spring_status",
        service="analyser",
        property="spring_status",
        device_class=SensorDeviceClass.ENUM,
        options=[
            status.name.lower()
            for status in SpringStatus
            if status != SpringStatus.UNKNOWN
        ],
        value_fn=lambda value: SpringStatus(value).name.lower() if value else None,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: FederwiegeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Smarla sensors from config entry."""
    federwiege = config_entry.runtime_data
    async_add_entities(
        (
            SmarlaSensor(federwiege, desc)
            if not desc.multiple
            else SmarlaSensorMultiple(federwiege, desc)
        )
        for desc in SENSORS
    )


class SmarlaSensor(SmarlaBaseEntity, SensorEntity):
    """Representation of Smarla sensor."""

    entity_description: SmarlaSensorEntityDescription

    _property: Property[int]

    @property
    def native_value(self) -> StateType:
        """Return the entity value to represent the entity state."""
        value = self._property.get()
        return self.entity_description.value_fn(value)


class SmarlaSensorMultiple(SmarlaBaseEntity, SensorEntity):
    """Representation of Smarla sensor with multiple values inside property."""

    entity_description: SmarlaSensorEntityDescription

    _property: Property[list[int]]

    @property
    def native_value(self) -> StateType:
        """Return the entity value to represent the entity state."""
        raw = self._property.get()
        value = raw[self.entity_description.value_pos] if raw is not None else None
        return self.entity_description.value_fn(value)
