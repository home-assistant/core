"""Sensor component for LaCrosse View."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from lacrosse_view import Sensor

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE
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

    value_fn: Callable[[Sensor, str], float]


@dataclass
class LaCrosseSensorEntityDescription(
    SensorEntityDescription, LaCrosseSensorEntityDescriptionMixin
):
    """Description for LaCrosse View sensor."""


def get_value(sensor: Sensor, field: str) -> float:
    """Get the value of a sensor field."""
    return float(sensor.data[field]["values"][-1]["s"])


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
SENSOR_DESCRIPTIONS = {
    "Temperature": LaCrosseSensorEntityDescription(
        key="",
        device_class=SensorDeviceClass.TEMPERATURE,
        name="Temperature",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=get_value,
        native_unit_of_measurement="°C",
    ),
    "Humidity": LaCrosseSensorEntityDescription(
        key="",
        device_class=SensorDeviceClass.HUMIDITY,
        name="Humidity",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=get_value,
        native_unit_of_measurement="%",
    ),
    "HeatIndex": LaCrosseSensorEntityDescription(
        key="",
        device_class=SensorDeviceClass.TEMPERATURE,
        name="Heat Index",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=get_value,
        native_unit_of_measurement="°F",
    ),
    "WindSpeed": LaCrosseSensorEntityDescription(
        key="",
        name="Wind Speed",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=get_value,
        native_unit_of_measurement="km/h",
    ),
    "Rain": LaCrosseSensorEntityDescription(
        key="",
        name="Rain",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=get_value,
        native_unit_of_measurement="in",
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up LaCrosse View from a config entry."""
    coordinator: DataUpdateCoordinator[list[Sensor]] = hass.data[DOMAIN][
        entry.entry_id
    ]["coordinator"]
    sensors: list[Sensor] = coordinator.data

    sensor_list = []
    for i, sensor in enumerate(sensors):
        for field in sensor.sensor_field_names:
            description = SENSOR_DESCRIPTIONS.get(field, None)
            if description is None:
                message = f"Unsupported sensor field: {field}\nPlease create an issue on GitHub. https://github.com/home-assistant/core/issues/new?assignees=&labels=&template=bug_report.yml&integration_name=LaCrosse%20View&integration_link=https://www.home-assistant.io/integrations/lacrosse_view/&additional_information=Field:%20{field}%0ASensor%20Model:%20{sensor.model}&title=LaCrosse%20View%20Unsupported%20sensor%20field:%20{field}"
                LOGGER.warning(message)
                return
            description.key = str(i)
            sensor_list.append(
                LaCrosseViewSensor(
                    coordinator=coordinator,
                    description=description,
                    field=field,
                )
            )

    async_add_entities(sensor_list)


class LaCrosseViewSensor(
    CoordinatorEntity[DataUpdateCoordinator[list[Sensor]]], SensorEntity
):
    """LaCrosse View sensor."""

    entity_description: LaCrosseSensorEntityDescription
    _sensor: Sensor
    _field: str

    def __init__(
        self,
        description: LaCrosseSensorEntityDescription,
        coordinator: DataUpdateCoordinator[list[Sensor]],
        field: str,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)

        sensor = self.coordinator.data[int(description.key)]

        if not sensor.permissions.get("read"):
            LOGGER.warning(
                "No permission to read sensor %s, are you sure you're signed into the right account?",
                sensor.name,
            )

        self.entity_description = description
        self._attr_unique_id = f"{sensor.location.id}-{description.key}-{field}"
        self._attr_name = f"{sensor.location.name} {description.name}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, sensor.sensor_id)},
            "name": sensor.name.split(" ")[0],
            "manufacturer": "LaCrosse Technology",
            "model": sensor.model,
            "via_device": (DOMAIN, sensor.location.id),
        }
        self._sensor = sensor
        self._field = field

    @property
    def native_value(self) -> float | str:
        """Return the sensor value."""
        if not self._sensor.permissions.get("read"):
            return STATE_UNAVAILABLE
        return self.entity_description.value_fn(self._sensor, self._field)
