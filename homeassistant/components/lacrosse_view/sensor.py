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
from homeassistant.const import (
    PERCENTAGE,
    PRECIPITATION_INCHES,
    SPEED_KILOMETERS_PER_HOUR,
    SPEED_MILES_PER_HOUR,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, LOGGER
from .coordinator import LaCrosseUpdateCoordinator


@dataclass
class LaCrosseSensorEntityDescriptionMixin:
    """Mixin for required keys."""

    value_fn: Callable[[Sensor, str], float | str]
    unit_metric: str | None
    unit_imperial: str | None


@dataclass
class LaCrosseSensorEntityDescription(
    SensorEntityDescription, LaCrosseSensorEntityDescriptionMixin
):
    """Description for LaCrosse View sensor."""


def get_value(sensor: Sensor, field: str) -> float:
    """Get the value of a sensor field."""
    return float(sensor.data[field]["values"][-1]["s"])


PARALLEL_UPDATES = 0
SENSOR_DESCRIPTIONS = {
    "Temperature": LaCrosseSensorEntityDescription(
        key="Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        name="Temperature",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=get_value,
        native_unit_of_measurement=TEMP_CELSIUS,
        unit_metric=None,  # For temperature devices, the unit is already changed based on user preference
        unit_imperial=None,
    ),
    "Humidity": LaCrosseSensorEntityDescription(
        key="Humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        name="Humidity",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=get_value,
        native_unit_of_measurement=PERCENTAGE,
        unit_metric=None,
        unit_imperial=None,
    ),
    "HeatIndex": LaCrosseSensorEntityDescription(
        key="HeatIndex",
        device_class=SensorDeviceClass.TEMPERATURE,
        name="Heat Index",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=get_value,
        native_unit_of_measurement=TEMP_FAHRENHEIT,
        unit_metric=None,
        unit_imperial=None,
    ),
    "WindSpeed": LaCrosseSensorEntityDescription(
        key="WindSpeed",
        name="Wind Speed",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=get_value,
        unit_metric=SPEED_KILOMETERS_PER_HOUR,
        unit_imperial=SPEED_MILES_PER_HOUR,
        icon="mdi:weather-windy",
    ),
    "Rain": LaCrosseSensorEntityDescription(
        key="Rain",
        name="Rain",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=get_value,
        native_unit_of_measurement=PRECIPITATION_INCHES,
        unit_metric=None,
        unit_imperial=None,
        icon="mdi:weather-rainy",
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up LaCrosse View from a config entry."""
    coordinator: LaCrosseUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        "coordinator"
    ]
    sensors: list[Sensor] = coordinator.data

    sensor_list = []
    for sensor in sensors:
        for field in sensor.sensor_field_names:
            description = SENSOR_DESCRIPTIONS.get(field)
            if description is None:
                message = (
                    f"Unsupported sensor field: {field}\nPlease create an issue on "
                    "GitHub. https://github.com/home-assistant/core/issues/new?assignees=&la"
                    "bels=&template=bug_report.yml&integration_name=LaCrosse%20View&integrat"
                    "ion_link=https://www.home-assistant.io/integrations/lacrosse_view/&addi"
                    f"tional_information=Field:%20{field}%0ASensor%20Model:%20{sensor.model}&"
                    f"title=LaCrosse%20View%20Unsupported%20sensor%20field:%20{field}"
                )

                LOGGER.warning(message)
                continue
            sensor_list.append(
                LaCrosseViewSensor(
                    coordinator=coordinator,
                    description=description,
                    sensor=sensor,
                )
            )

    async_add_entities(sensor_list)


class LaCrosseViewSensor(CoordinatorEntity[LaCrosseUpdateCoordinator], SensorEntity):
    """LaCrosse View sensor."""

    entity_description: LaCrosseSensorEntityDescription

    def __init__(
        self,
        description: LaCrosseSensorEntityDescription,
        coordinator: LaCrosseUpdateCoordinator,
        sensor: Sensor,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)

        self.entity_description = description
        self._attr_unique_id = f"{sensor.sensor_id}-{description.key}"
        self._attr_name = f"{sensor.location.name} {description.name}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, sensor.sensor_id)},
            "name": sensor.name.split(" ")[0],
            "manufacturer": "LaCrosse Technology",
            "model": sensor.model,
            "via_device": (DOMAIN, sensor.location.id),
        }
        self._sensor = sensor

        if description.unit_metric is not None:
            self._attr_native_unit_of_measurement = (
                SPEED_KILOMETERS_PER_HOUR
                if coordinator.is_metric
                else SPEED_MILES_PER_HOUR
            )

    @property
    def native_value(self) -> float | str:
        """Return the sensor value."""
        return self.entity_description.value_fn(
            self._sensor, self.entity_description.key
        )
