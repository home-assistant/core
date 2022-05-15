"""Sensor component for LaCrosse View."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from re import sub

from lacrosse_view import Sensor

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DOMAIN, LOGGER


@dataclass
class LaCrosseSensorEntityDescriptionMixin:
    """Mixin for required keys."""

    value_fn: Callable[[Sensor, str], int]


@dataclass
class LaCrosseSensorEntityDescription(
    SensorEntityDescription, LaCrosseSensorEntityDescriptionMixin
):
    """Description for LaCrosse View sensor."""


PARALLEL_UPDATES = 0
ICON_LIST = {
    "Temperature": "mdi:thermometer",
    "Humidity": "mdi:water-percent",
    "HeatIndex": "mdi:thermometer",
    "WindSpeed": "mdi:weather-windy",
    "Rain": "mdi:water",
}
UNIT_LIST = {
    "degrees_celsius": "°C",
    "degrees_fahrenheit": "°F",
    "relative_humidity": "%",
    "kilometers_per_hour": "km/h",
    "inches": "in",
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up LaCrosse View from a config entry."""
    coordinator: DataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        "coordinator"
    ]
    sensors: list[Sensor] = coordinator.data

    sensor_list = []
    for i, sensor in enumerate(sensors):
        if not sensor.permissions.get("read"):
            LOGGER.warning(
                "No permission to read sensor %s, are you sure you're signed into the right account?",
                sensor.name,
            )
        for field in sensor.sensor_field_names:
            sensor_list.append(
                LaCrosseViewSensor(
                    coordinator=coordinator,
                    description=LaCrosseSensorEntityDescription(
                        key=f"{i} {field}",
                        device_class="temperature" if field == "Temperature" else None,
                        name=f"{sensor.name} {sub(r'(?<!^)(?=[A-Z])', ' ', field)}"
                        if field
                        != sensor.name  # If the name is the same as the field, don't include it.
                        else sub(r"(?<!^)(?=[A-Z])", " ", field),
                        state_class=SensorStateClass.MEASUREMENT,
                        value_fn=lambda sensor, field: sensor.data[field]["values"][-1][
                            "s"
                        ],
                        native_unit_of_measurement=UNIT_LIST.get(
                            sensor.data[field]["unit"], None
                        ),
                    ),
                )
            )

    async_add_entities(sensor_list)


class LaCrosseViewSensor(
    CoordinatorEntity[DataUpdateCoordinator[list[Sensor]]], SensorEntity
):
    """LaCrosse View sensor."""

    sensor_index: int = 0
    entity_description: LaCrosseSensorEntityDescription

    def __init__(
        self,
        description: LaCrosseSensorEntityDescription,
        coordinator: DataUpdateCoordinator[list[Sensor]],
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        sensor = self.coordinator.data[int(description.key.split(" ")[0])]

        self.entity_description = description
        self._attr_unique_id = f"{coordinator.data[0].location.id}-{description.key}"
        self._attr_name = f"{coordinator.data[0].location.name} {description.name}"
        self._attr_icon = ICON_LIST.get(
            description.key.split(" ")[1], "mdi:thermometer"
        )
        self._attr_device_info = {
            "identifiers": {(DOMAIN, sensor.sensor_id)},
            "name": sensor.name.split(" ")[0],
            "manufacturer": "LaCrosse Technology",
            "model": sensor.model,
            "via_device": (DOMAIN, sensor.location.id),
        }

    @property
    def native_value(self) -> int:
        """Return the sensor value."""
        return self.entity_description.value_fn(
            self.coordinator.data[int(self.entity_description.key.split(" ")[0])],
            self.entity_description.key.split(" ")[1],
        )
