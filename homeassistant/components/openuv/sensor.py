"""Support for OpenUV sensors."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UV_INDEX, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.dt import as_local, parse_datetime

from .const import (
    DATA_UV,
    DOMAIN,
    TYPE_CURRENT_OZONE_LEVEL,
    TYPE_CURRENT_UV_INDEX,
    TYPE_CURRENT_UV_LEVEL,
    TYPE_MAX_UV_INDEX,
    TYPE_SAFE_EXPOSURE_TIME_1,
    TYPE_SAFE_EXPOSURE_TIME_2,
    TYPE_SAFE_EXPOSURE_TIME_3,
    TYPE_SAFE_EXPOSURE_TIME_4,
    TYPE_SAFE_EXPOSURE_TIME_5,
    TYPE_SAFE_EXPOSURE_TIME_6,
)
from .coordinator import OpenUvCoordinator
from .entity import OpenUvEntity

ATTR_MAX_UV_TIME = "time"

EXPOSURE_TYPE_MAP = {
    TYPE_SAFE_EXPOSURE_TIME_1: "st1",
    TYPE_SAFE_EXPOSURE_TIME_2: "st2",
    TYPE_SAFE_EXPOSURE_TIME_3: "st3",
    TYPE_SAFE_EXPOSURE_TIME_4: "st4",
    TYPE_SAFE_EXPOSURE_TIME_5: "st5",
    TYPE_SAFE_EXPOSURE_TIME_6: "st6",
}


@dataclass
class UvLabel:
    """Define a friendly UV level label and its minimum UV index."""

    value: str
    minimum_index: int


UV_LABEL_DEFINITIONS = (
    UvLabel(value="extreme", minimum_index=11),
    UvLabel(value="very_high", minimum_index=8),
    UvLabel(value="high", minimum_index=6),
    UvLabel(value="moderate", minimum_index=3),
    UvLabel(value="low", minimum_index=0),
)


def get_uv_label(uv_index: int) -> str:
    """Return the UV label for the UV index."""
    label = next(
        label for label in UV_LABEL_DEFINITIONS if uv_index >= label.minimum_index
    )
    return label.value


@dataclass(frozen=True, kw_only=True)
class OpenUvSensorEntityDescription(SensorEntityDescription):
    """Define a class that describes OpenUV sensor entities."""

    value_fn: Callable[[dict[str, Any]], int | str]


SENSOR_DESCRIPTIONS = (
    OpenUvSensorEntityDescription(
        key=TYPE_CURRENT_OZONE_LEVEL,
        translation_key="current_ozone_level",
        native_unit_of_measurement="du",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data["ozone"],
    ),
    OpenUvSensorEntityDescription(
        key=TYPE_CURRENT_UV_INDEX,
        translation_key="current_uv_index",
        native_unit_of_measurement=UV_INDEX,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data["uv"],
    ),
    OpenUvSensorEntityDescription(
        key=TYPE_CURRENT_UV_LEVEL,
        translation_key="current_uv_level",
        device_class=SensorDeviceClass.ENUM,
        options=[label.value for label in UV_LABEL_DEFINITIONS],
        value_fn=lambda data: get_uv_label(data["uv"]),
    ),
    OpenUvSensorEntityDescription(
        key=TYPE_MAX_UV_INDEX,
        translation_key="max_uv_index",
        native_unit_of_measurement=UV_INDEX,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data["uv_max"],
    ),
    OpenUvSensorEntityDescription(
        key=TYPE_SAFE_EXPOSURE_TIME_1,
        translation_key="skin_type_1_safe_exposure_time",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data["safe_exposure_time"][
            EXPOSURE_TYPE_MAP[TYPE_SAFE_EXPOSURE_TIME_1]
        ],
    ),
    OpenUvSensorEntityDescription(
        key=TYPE_SAFE_EXPOSURE_TIME_2,
        translation_key="skin_type_2_safe_exposure_time",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data["safe_exposure_time"][
            EXPOSURE_TYPE_MAP[TYPE_SAFE_EXPOSURE_TIME_2]
        ],
    ),
    OpenUvSensorEntityDescription(
        key=TYPE_SAFE_EXPOSURE_TIME_3,
        translation_key="skin_type_3_safe_exposure_time",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data["safe_exposure_time"][
            EXPOSURE_TYPE_MAP[TYPE_SAFE_EXPOSURE_TIME_3]
        ],
    ),
    OpenUvSensorEntityDescription(
        key=TYPE_SAFE_EXPOSURE_TIME_4,
        translation_key="skin_type_4_safe_exposure_time",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data["safe_exposure_time"][
            EXPOSURE_TYPE_MAP[TYPE_SAFE_EXPOSURE_TIME_4]
        ],
    ),
    OpenUvSensorEntityDescription(
        key=TYPE_SAFE_EXPOSURE_TIME_5,
        translation_key="skin_type_5_safe_exposure_time",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data["safe_exposure_time"][
            EXPOSURE_TYPE_MAP[TYPE_SAFE_EXPOSURE_TIME_5]
        ],
    ),
    OpenUvSensorEntityDescription(
        key=TYPE_SAFE_EXPOSURE_TIME_6,
        translation_key="skin_type_6_safe_exposure_time",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data["safe_exposure_time"][
            EXPOSURE_TYPE_MAP[TYPE_SAFE_EXPOSURE_TIME_6]
        ],
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up a OpenUV sensor based on a config entry."""
    coordinators: dict[str, OpenUvCoordinator] = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        [
            OpenUvSensor(coordinators[DATA_UV], description)
            for description in SENSOR_DESCRIPTIONS
        ]
    )


class OpenUvSensor(OpenUvEntity, SensorEntity):
    """Define a binary sensor for OpenUV."""

    entity_description: OpenUvSensorEntityDescription

    @property
    def extra_state_attributes(self) -> Mapping[str, Any]:
        """Return entity specific state attributes."""
        attrs = {}
        if self.entity_description.key == TYPE_MAX_UV_INDEX:
            if uv_max_time := parse_datetime(self.coordinator.data["uv_max_time"]):
                attrs[ATTR_MAX_UV_TIME] = as_local(uv_max_time)
        return attrs

    @property
    def native_value(self) -> int | str:
        """Return the sensor value."""
        return self.entity_description.value_fn(self.coordinator.data)
