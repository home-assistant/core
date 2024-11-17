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


def get_uv_label_and_color(uv_index: int) -> tuple[str, str]:
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
        value_fn=lambda data: get_uv_label_and_color(data["uv"])[0],
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
    coordinators: dict[str, OpenUvCoordinator] = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        [
            OpenUvGraphSensor(coordinators[DATA_UV], description)
            if description.key == TYPE_CURRENT_UV_INDEX_WITH_GRAPH
            else OpenUvSensor(coordinators[DATA_UV], description)
            for description in SENSOR_DESCRIPTIONS
        ]
    )


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
            label, color = get_uv_label_and_color(uv_index)
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
        return value if isinstance(value, int) else 0

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
