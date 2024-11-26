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
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
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

SKIN_TYPE_TRANSLATION: dict[str, int | None] = {
    "Skin Type I": 0,
    "Skin Type II": 1,
    "Skin Type III": 2,
    "Skin Type IV": 3,
    "Skin Type V": 4,
    "Skin Type VI": 5,
}
UV_INDEX_LABEL_TRANSLATION: dict[str, int] = {
    "low": 0,
    "moderate": 1,
    "high": 2,
    "very_high": 3,
    "extreme": 4,
}

SUN_EXPOSURE: list[list[tuple[int, int] | None]] = [
    [(15, 20), (20, 30), (30, 40), (40, 60), (60, 80), None],
    [(10, 15), (15, 20), (20, 30), (30, 40), (40, 60), (60, 80)],
    [(5, 10), (10, 15), (15, 20), (20, 30), (30, 40), (40, 60)],
    [(2, 8), (5, 10), (10, 15), (15, 20), (20, 30), (30, 40)],
    [(1, 5), (2, 8), (5, 10), (10, 15), (15, 20), (20, 30)],
]


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
    entry_data = dict(entry.data)

    async_add_entities([SkinTypeSensor(entry_data, entry=entry)])

    coordinators: dict[str, OpenUvCoordinator] = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([VitaminDSensor(coordinators[DATA_UV])])
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


class SkinTypeSensor(SensorEntity):
    """Define a sensor that reflects the user's selected skin type."""

    def __init__(self, entry_data: dict, entry: ConfigEntry) -> None:
        """Initialize the Skin Type sensor."""
        self._attr_name = "Skin Type"
        self._attr_unique_id = (
            f"skin_type_{entry_data['latitude']}_{entry_data['longitude']}"
        )
        self._entry_data = dict(entry_data)
        self.entry = entry
        self._attr_device_info = DeviceInfo(
            identifiers={
                (DOMAIN, f"{entry_data['latitude']}_{entry_data['longitude']}")
            },
            name="OpenUV",
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def native_value(self) -> str:
        """Return the current state of the skin type sensor."""
        skin_type = self.entry.options.get("skin_type", None)
        if skin_type is None:
            skin_type = self._entry_data.get("skin_type", "None")
        return str(skin_type)

    @property
    def extra_state_attributes(self) -> Mapping[str, Any]:
        """Return extra state attributes."""
        return {
            "skin_type": self._entry_data.get("skin_type", "None"),
        }

    async def async_update(self) -> None:
        """Update the sensor state from the configuration."""
        skin_type = self.entry.options.get("skin_type", None)
        if skin_type is not None:
            self._entry_data["skin_type"] = skin_type
        self.async_write_ha_state()


class VitaminDSensor(SensorEntity):
    "Define a sensor for vitamin D intake."

    def __init__(self, coordinator: OpenUvCoordinator) -> None:
        "Initialize the Vitamin D sensor."
        self._attr_name = "Vitamin D Intake Sun Exposure"
        self._attr_unique_id = (
            f"vitamin_d_{coordinator.latitude}_{coordinator.longitude}"
        )
        self.coordinator = coordinator
        super().__init__()

    @property
    def native_value(self) -> str:
        """Get the value for vitamin D intake."""
        skin_type = self.coordinator.config_entry.options.get("skin_type", "None")
        current_uv_index_label = get_uv_label(self.coordinator.data["uv"])
        return self.get_sun_exposure(skin_type, current_uv_index_label)

    async def async_update(self) -> None:
        "Update the sensor data."
        self.async_write_ha_state()

    def get_sun_exposure(self, skin_type: str, current_uv_index: str) -> str:
        "Get recommended sun exposure to reach vitamin D intake."
        skin_type_translated: int | None = SKIN_TYPE_TRANSLATION.get(skin_type)
        uv_index_label_translated: int = UV_INDEX_LABEL_TRANSLATION.get(
            current_uv_index, 0
        )
        if skin_type_translated is None:
            return "Set your skin type"
        sun_exposure_interval: tuple[int, int] | None = SUN_EXPOSURE[
            uv_index_label_translated
        ][skin_type_translated]
        if sun_exposure_interval is None:
            return "-"
        return f"{sun_exposure_interval[0]} - {sun_exposure_interval[1]} min"
