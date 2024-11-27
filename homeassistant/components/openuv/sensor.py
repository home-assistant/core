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
    TYPE_CURRENT_UV_INDEX_WITH_GRAPH,
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
    color: str


UV_LABEL_DEFINITIONS = (
    UvLabel(value="extreme", minimum_index=11, color="purple"),
    UvLabel(value="very_high", minimum_index=8, color="red"),
    UvLabel(value="high", minimum_index=6, color="orange"),
    UvLabel(value="moderate", minimum_index=3, color="yellow"),
    UvLabel(value="low", minimum_index=0, color="green"),
)


def get_uv_label(uv_index: int) -> tuple[str, str]:
    """Return the UV label for the UV index."""
    label = next(
        label for label in UV_LABEL_DEFINITIONS if uv_index >= label.minimum_index
    )
    return label.value, label.color


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
        value_fn=lambda data: get_uv_label(data["uv"])[0],
    ),
    OpenUvSensorEntityDescription(
        key=TYPE_CURRENT_UV_INDEX_WITH_GRAPH,
        translation_key="current_uv_index_with_graph",
        native_unit_of_measurement=UV_INDEX,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data["uv"],
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
    async_add_entities([VitaminDSensor(coordinators[DATA_UV])])
    async_add_entities(
        [
            OpenUvGraphSensor(coordinators[DATA_UV], description)
            if description.key == TYPE_CURRENT_UV_INDEX_WITH_GRAPH
            else OpenUvSensor(coordinators[DATA_UV], description)
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
    """Define a sensor for OpenUV."""

    entity_description: OpenUvSensorEntityDescription

    @property
    def extra_state_attributes(self) -> Mapping[str, Any]:
        """Return entity specific state attributes."""
        attrs = {}
        if self.entity_description.key == TYPE_MAX_UV_INDEX:
            if uv_max_time := parse_datetime(self.coordinator.data["uv_max_time"]):
                attrs[ATTR_MAX_UV_TIME] = as_local(uv_max_time).isoformat()
        return attrs

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self.entity_description.translation_key or "OpenUV Sensor"

    @property
    def native_value(self) -> int | str:
        """Return the sensor value."""
        return self.entity_description.value_fn(self.coordinator.data)


class OpenUvGraphSensor(OpenUvEntity, SensorEntity):
    """Define a sensor for Current UV Index with Graph."""

    # Describe the sensor entity for OpenUV
    entity_description: OpenUvSensorEntityDescription

    def __init__(
        self, coordinator: OpenUvCoordinator, description: OpenUvSensorEntityDescription
    ) -> None:
        """Initialize the sensor.

        Args:
            coordinator (OpenUvCoordinator): The data coordinator for fetching UV data.
            description (OpenUvSensorEntityDescription): The description for the sensor entity.

        """
        super().__init__(coordinator, description)
        # Store hourly forecast data as a list of dictionaries (e.g., [{"time": "10:00", "uv_index": 5}])
        self._hourly_forecast: list[dict[str, Any]] = []

    @property
    def extra_state_attributes(self) -> Mapping[str, Any]:
        """Return entity-specific state attributes for UV Index with Graph.

        Returns:
            Mapping[str, Any]: Additional attributes including risk color, label, and hourly forecast.

        """
        attrs: dict[str, Any] = {}

        # Retrieve the current UV Index value
        uv_index = self.native_value
        if uv_index is not None and isinstance(uv_index, int):
            # Get the corresponding risk label and color for the UV Index
            label, color = get_uv_label(uv_index)
            attrs["color"] = color  # Add color to attributes (e.g., "green", "yellow")
            attrs["uv_label"] = label  # Add risk level label (e.g., "low", "moderate")

        # Include the hourly forecast data in the attributes if it exists
        if self._hourly_forecast:
            attrs["hourly_uv_index"] = self._hourly_forecast

        return attrs

    @property
    def name(self) -> str:
        """Return the name of the sensor.

        Returns:
            str: The name displayed in the Home Assistant UI.

        """
        return "Current UV Index with Graph"

    @property
    def unique_id(self) -> str:
        """Return a unique ID for the sensor.

        Returns:
            str: A unique identifier for the sensor entity.

        """
        return "current_uv_index_with_graph"

    @property
    def native_value(self) -> int:
        """Return the current UV Index value.

        Returns:
            int: The current UV Index. Defaults to 0 if value is invalid.

        """
        value = self.entity_description.value_fn(self.coordinator.data)
        return value if isinstance(value, (int, float)) else 0

    async def async_update(self) -> None:
        """Fetch data dynamically and update the UV Index and hourly forecast.

        This method is called automatically by the data coordinator to refresh the sensor's data.
        """
        # Call the parent class's update method to sync with the data coordinator
        await super().async_update()

        # Clear the existing forecast data
        self._hourly_forecast = []

        # Fetch UV Index time series data from the coordinator
        data: dict[str, Any] = self.coordinator.data

        # Check if "uv_time_series" exists in the data and is a list
        if "uv_time_series" in data and isinstance(data["uv_time_series"], list):
            for entry in data["uv_time_series"]:
                # Extract the time (HH:MM format) from the timestamp
                time = entry.get("time", "").split("T")[1][:5]  # Example: "10:00"
                # Extract the UV Index value
                uv_index = entry.get("uv", 0)
                # Append the time and UV Index as a dictionary to the hourly forecast
                self._hourly_forecast.append({"time": time, "uv_index": uv_index})


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
        current_uv_index_label = get_uv_label(self.coordinator.data["uv"])[0]
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
