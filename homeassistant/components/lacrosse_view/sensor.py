"""Sensor component for LaCrosse View."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging

from lacrosse_view import Sensor

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    DEGREE,
    PERCENTAGE,
    UnitOfPrecipitationDepth,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


@dataclass
class LaCrosseSensorEntityDescriptionMixin:
    """Mixin for required keys."""

    value_fn: Callable[[Sensor, str], float | int | str | None]


@dataclass
class LaCrosseSensorEntityDescription(
    SensorEntityDescription, LaCrosseSensorEntityDescriptionMixin
):
    """Description for LaCrosse View sensor."""


def get_value(sensor: Sensor, field: str) -> float | int | str | None:
    """Get the value of a sensor field."""
    field_data = sensor.data.get(field)
    if field_data is None:
        return None
    value = field_data["values"][-1]["s"]
    try:
        value = float(value)
    except ValueError:
        return str(value)  # handle non-numericals
    return int(value) if value.is_integer() else value


PARALLEL_UPDATES = 0
SENSOR_DESCRIPTIONS = {
    "Temperature": LaCrosseSensorEntityDescription(
        key="Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=get_value,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    "Humidity": LaCrosseSensorEntityDescription(
        key="Humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=get_value,
        native_unit_of_measurement=PERCENTAGE,
    ),
    "HeatIndex": LaCrosseSensorEntityDescription(
        key="HeatIndex",
        translation_key="heat_index",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=get_value,
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
    ),
    "WindSpeed": LaCrosseSensorEntityDescription(
        key="WindSpeed",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=get_value,
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        device_class=SensorDeviceClass.WIND_SPEED,
    ),
    "Rain": LaCrosseSensorEntityDescription(
        key="Rain",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=get_value,
        native_unit_of_measurement=UnitOfPrecipitationDepth.INCHES,
        device_class=SensorDeviceClass.PRECIPITATION,
    ),
    "WindHeading": LaCrosseSensorEntityDescription(
        key="WindHeading",
        translation_key="wind_heading",
        value_fn=get_value,
        native_unit_of_measurement=DEGREE,
    ),
    "WetDry": LaCrosseSensorEntityDescription(
        key="WetDry",
        translation_key="wet_dry",
        value_fn=get_value,
    ),
    "Flex": LaCrosseSensorEntityDescription(
        key="Flex",
        translation_key="flex",
        value_fn=get_value,
    ),
    "BarometricPressure": LaCrosseSensorEntityDescription(
        key="BarometricPressure",
        translation_key="barometric_pressure",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=get_value,
        device_class=SensorDeviceClass.ATMOSPHERIC_PRESSURE,
        native_unit_of_measurement=UnitOfPressure.HPA,
    ),
    "FeelsLike": LaCrosseSensorEntityDescription(
        key="FeelsLike",
        translation_key="feels_like",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=get_value,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    "WindChill": LaCrosseSensorEntityDescription(
        key="WindChill",
        translation_key="wind_chill",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=get_value,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
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
            description = SENSOR_DESCRIPTIONS.get(field)
            if description is None:
                message = (
                    f"Unsupported sensor field: {field}\nPlease create an issue on "
                    "GitHub."
                    " https://github.com/home-assistant/core/issues/new?assignees=&la"
                    "bels=&template=bug_report.yml&integration_name=LaCrosse%20View&integrat"
                    "ion_link=https://www.home-assistant.io/integrations/lacrosse_view/&addi"
                    f"tional_information=Field:%20{field}%0ASensor%20Model:%20{sensor.model}&"
                    f"title=LaCrosse%20View%20Unsupported%20sensor%20field:%20{field}"
                )

                _LOGGER.warning(message)
                continue
            sensor_list.append(
                LaCrosseViewSensor(
                    coordinator=coordinator,
                    description=description,
                    sensor=sensor,
                    index=i,
                )
            )

    async_add_entities(sensor_list)


class LaCrosseViewSensor(
    CoordinatorEntity[DataUpdateCoordinator[list[Sensor]]], SensorEntity
):
    """LaCrosse View sensor."""

    entity_description: LaCrosseSensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        description: LaCrosseSensorEntityDescription,
        coordinator: DataUpdateCoordinator[list[Sensor]],
        sensor: Sensor,
        index: int,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)

        self.entity_description = description
        self._attr_unique_id = f"{sensor.sensor_id}-{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, sensor.sensor_id)},
            name=sensor.name,
            manufacturer="LaCrosse Technology",
            model=sensor.model,
            via_device=(DOMAIN, sensor.location.id),
        )
        self.index = index

    @property
    def native_value(self) -> int | float | str | None:
        """Return the sensor value."""
        return self.entity_description.value_fn(
            self.coordinator.data[self.index], self.entity_description.key
        )

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return (
            super().available
            and self.entity_description.key in self.coordinator.data[self.index].data
        )
