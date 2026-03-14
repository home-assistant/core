"""Support for the Swing2Sleep Smarla sensor entities."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Generic, TypeVar

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

_VT = TypeVar("_VT")


@dataclass(frozen=True, kw_only=True)
class SmarlaSensorEntityDescription(
    SmarlaEntityDescription, SensorEntityDescription, Generic[_VT]
):
    """Class describing Swing2Sleep Smarla sensor entities."""

    value_fn: Callable[[_VT | None], StateType] = lambda value: (
        value if isinstance(value, (str, int, float)) else None
    )


SENSORS: list[SmarlaSensorEntityDescription[Any]] = [
    SmarlaSensorEntityDescription[list[int]](
        key="amplitude",
        translation_key="amplitude",
        service="analyser",
        property="oscillation",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.MILLIMETERS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda value: value[0] if value else None,
    ),
    SmarlaSensorEntityDescription[list[int]](
        key="period",
        translation_key="period",
        service="analyser",
        property="oscillation",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MILLISECONDS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda value: value[1] if value else None,
    ),
    SmarlaSensorEntityDescription[int](
        key="activity",
        translation_key="activity",
        service="analyser",
        property="activity",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SmarlaSensorEntityDescription[int](
        key="swing_count",
        translation_key="swing_count",
        service="analyser",
        property="swing_count",
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SmarlaSensorEntityDescription[int](
        key="total_swing_time",
        translation_key="total_swing_time",
        service="info",
        property="total_swing_time",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_unit_of_measurement=UnitOfTime.HOURS,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SmarlaSensorEntityDescription[SpringStatus](
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
        value_fn=lambda value: (
            value.name.lower() if value and value != SpringStatus.UNKNOWN else None
        ),
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: FederwiegeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Smarla sensors from config entry."""
    federwiege = config_entry.runtime_data
    async_add_entities(SmarlaSensor(federwiege, desc) for desc in SENSORS)


class SmarlaSensor(SmarlaBaseEntity, SensorEntity, Generic[_VT]):
    """Representation of Smarla sensor."""

    entity_description: SmarlaSensorEntityDescription[_VT]

    _property: Property[_VT]

    @property
    def native_value(self) -> StateType:
        """Return the entity value to represent the entity state."""
        value = self._property.get()
        return self.entity_description.value_fn(value)
