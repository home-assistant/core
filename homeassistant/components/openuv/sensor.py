"""Support for OpenUV sensors."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
import logging
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
from homeassistant.helpers import entity_registry as er
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

# Set up a logger for your component
_LOGGER = logging.getLogger(__name__)

ATTR_MAX_UV_TIME = "time"

EXPOSURE_TYPE_MAP = {
    TYPE_SAFE_EXPOSURE_TIME_1: "st1",
    TYPE_SAFE_EXPOSURE_TIME_2: "st2",
    TYPE_SAFE_EXPOSURE_TIME_3: "st3",
    TYPE_SAFE_EXPOSURE_TIME_4: "st4",
    TYPE_SAFE_EXPOSURE_TIME_5: "st5",
    TYPE_SAFE_EXPOSURE_TIME_6: "st6",
}
# Roman numeral to integer mapping for skin types
roman_to_int = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6}


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
    """Set up OpenUV sensors based on a config entry."""
    entry_data = dict(entry.data)

    async_add_entities([SkinTypeSensor(entry_data, entry=entry)])

    coordinators: dict[str, OpenUvCoordinator] = hass.data[DOMAIN][entry.entry_id]

    skin_type = entry.options.get("skin_type", None) or entry_data.get(
        "skin_type", "None"
    )

    async_add_entities(
        [
            OpenUvSensor(coordinators[DATA_UV], description)
            for description in SENSOR_DESCRIPTIONS
            if description.translation_key
            and "safe_exposure_time" not in description.translation_key
        ]
    )

    existing_entities = set(hass.states.async_entity_ids("sensor"))

    if skin_type == "None":
        add_all_safe_exposure_sensors(
            existing_entities, async_add_entities, coordinators
        )
    else:
        add_specific_safe_exposure_sensor(
            skin_type, existing_entities, async_add_entities, coordinators
        )

    # When setting the update listener, pass `async_add_entities` correctly.
    entry.async_on_unload(
        entry.add_update_listener(
            lambda hass, entry: options_update_listener(hass, entry, async_add_entities)
        )
    )


def add_all_safe_exposure_sensors(
    existing_entities: set, async_add_entities: AddEntitiesCallback, coordinators: dict
) -> None:
    """Add all safe exposure time sensors (for skin types I–VI) if they don't already exist."""
    for i in range(1, 7):
        if f"sensor.type_safe_exposure_time_{i}" not in existing_entities:
            sensor_description = get_sensor_description_for_skin_type(i)
            sensor = OpenUvSensor(coordinators[DATA_UV], sensor_description)
            async_add_entities([sensor], update_before_add=True)


def add_specific_safe_exposure_sensor(
    skin_type: str,
    existing_entities: set,
    async_add_entities: AddEntitiesCallback,
    coordinators: dict,
) -> None:
    """Add a specific safe exposure time sensor based on the selected skin type."""
    roman_part = skin_type.split(" ")[-1]
    selected_type = roman_to_int.get(roman_part)

    if selected_type:
        if f"sensor.type_safe_exposure_time_{selected_type}" not in existing_entities:
            # Reference the existing sensor description instead of creating one dynamically
            sensor_description = get_sensor_description_for_skin_type(selected_type)
            sensor = OpenUvSensor(coordinators[DATA_UV], sensor_description)
            async_add_entities([sensor], update_before_add=True)
    else:
        _LOGGER.warning("Invalid skin type")


def get_sensor_description_for_skin_type(
    skin_type_number: int,
) -> OpenUvSensorEntityDescription:
    """Retrieve the predefined sensor description for a given skin type."""
    for description in SENSOR_DESCRIPTIONS:
        if (
            description.translation_key
            == f"skin_type_{skin_type_number}_safe_exposure_time"
        ):
            return description
    raise ValueError(f"Sensor description for skin type {skin_type_number} not found")


async def options_update_listener(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Handle options update for skin type changes."""

    skin_type = entry.options.get("skin_type", "None")
    coordinators = hass.data[DOMAIN][entry.entry_id]
    entity_registry = er.async_get(hass)

    if skin_type == "None":
        for i in range(1, 7):
            entity_id = f"sensor.openuv_skin_type_{i}_safe_exposure_time"
            if not entity_registry.async_is_registered(entity_id):
                sensordescription = get_safe_exposure_sensor(coordinators, i)
                async_add_entities([sensordescription])
    else:
        roman_part = skin_type.split(" ")[-1]
        selected_type = roman_to_int.get(roman_part)

        if selected_type:
            entity_id = f"sensor.openuv_skin_type_{selected_type}_safe_exposure_time"
            if not entity_registry.async_is_registered(entity_id):
                sensordescription = get_safe_exposure_sensor(
                    coordinators, selected_type
                )
                async_add_entities([sensordescription])

            # Remove all other safe exposure sensors
            for i in range(1, 7):
                if i != selected_type:
                    other_entity_id = f"sensor.openuv_skin_type_{i}_safe_exposure_time"
                    if entity_registry.async_is_registered(other_entity_id):
                        entity_registry.async_remove(other_entity_id)
        else:
            _LOGGER.warning("Invalid skin type")


def get_safe_exposure_sensor(
    coordinators: dict,
    skin_type_number: int,
) -> OpenUvSensor:
    """Add a safe exposure sensor for a given skin type."""
    sensor_description = get_sensor_description_for_skin_type(skin_type_number)
    return OpenUvSensor(coordinators[DATA_UV], sensor_description)


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
