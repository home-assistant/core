"""Support for the AEMET OpenData service."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Final

from aemet_opendata.const import (
    AOD_CONDITION,
    AOD_FEEL_TEMP,
    AOD_FORECAST_CURRENT,
    AOD_FORECAST_DAILY,
    AOD_FORECAST_HOURLY,
    AOD_HUMIDITY,
    AOD_ID,
    AOD_NAME,
    AOD_PRECIPITATION,
    AOD_PRECIPITATION_PROBABILITY,
    AOD_PRESSURE,
    AOD_RAIN,
    AOD_RAIN_PROBABILITY,
    AOD_SNOW,
    AOD_SNOW_PROBABILITY,
    AOD_STATION,
    AOD_STORM_PROBABILITY,
    AOD_TEMP,
    AOD_TEMP_MAX,
    AOD_TEMP_MIN,
    AOD_TIMESTAMP_UTC,
    AOD_TOWN,
    AOD_WEATHER,
    AOD_WIND_DIRECTION,
    AOD_WIND_SPEED,
    AOD_WIND_SPEED_MAX,
)
from aemet_opendata.helpers import dict_nested_value

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    DEGREE,
    PERCENTAGE,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
    UnitOfVolumetricFlux,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from . import AemetConfigEntry
from .const import (
    ATTR_API_CONDITION,
    ATTR_API_FORECAST_CONDITION,
    ATTR_API_FORECAST_PRECIPITATION,
    ATTR_API_FORECAST_PRECIPITATION_PROBABILITY,
    ATTR_API_FORECAST_TEMP,
    ATTR_API_FORECAST_TEMP_LOW,
    ATTR_API_FORECAST_TIME,
    ATTR_API_FORECAST_WIND_BEARING,
    ATTR_API_FORECAST_WIND_MAX_SPEED,
    ATTR_API_FORECAST_WIND_SPEED,
    ATTR_API_HUMIDITY,
    ATTR_API_PRESSURE,
    ATTR_API_RAIN,
    ATTR_API_RAIN_PROB,
    ATTR_API_SNOW,
    ATTR_API_SNOW_PROB,
    ATTR_API_STATION_ID,
    ATTR_API_STATION_NAME,
    ATTR_API_STATION_TIMESTAMP,
    ATTR_API_STORM_PROB,
    ATTR_API_TEMPERATURE,
    ATTR_API_TEMPERATURE_FEELING,
    ATTR_API_TOWN_ID,
    ATTR_API_TOWN_NAME,
    ATTR_API_TOWN_TIMESTAMP,
    ATTR_API_WIND_BEARING,
    ATTR_API_WIND_MAX_SPEED,
    ATTR_API_WIND_SPEED,
    CONDITIONS_MAP,
)
from .coordinator import WeatherUpdateCoordinator
from .entity import AemetEntity


@dataclass(frozen=True, kw_only=True)
class AemetSensorEntityDescription(SensorEntityDescription):
    """A class that describes AEMET OpenData sensor entities."""

    keys: list[str] | None = None
    value_fn: Callable[[str], datetime | float | int | str | None] = lambda value: value


FORECAST_SENSORS: Final[tuple[AemetSensorEntityDescription, ...]] = (
    AemetSensorEntityDescription(
        key=f"forecast-daily-{ATTR_API_FORECAST_CONDITION}",
        keys=[AOD_TOWN, AOD_FORECAST_DAILY, AOD_FORECAST_CURRENT, AOD_CONDITION],
        name="Daily forecast condition",
        value_fn=CONDITIONS_MAP.get,
    ),
    AemetSensorEntityDescription(
        entity_registry_enabled_default=False,
        key=f"forecast-hourly-{ATTR_API_FORECAST_CONDITION}",
        keys=[AOD_TOWN, AOD_FORECAST_HOURLY, AOD_FORECAST_CURRENT, AOD_CONDITION],
        name="Hourly forecast condition",
        value_fn=CONDITIONS_MAP.get,
    ),
    AemetSensorEntityDescription(
        entity_registry_enabled_default=False,
        key=f"forecast-hourly-{ATTR_API_FORECAST_PRECIPITATION}",
        keys=[AOD_TOWN, AOD_FORECAST_HOURLY, AOD_FORECAST_CURRENT, AOD_PRECIPITATION],
        name="Hourly forecast precipitation",
        native_unit_of_measurement=UnitOfVolumetricFlux.MILLIMETERS_PER_HOUR,
        device_class=SensorDeviceClass.PRECIPITATION_INTENSITY,
    ),
    AemetSensorEntityDescription(
        key=f"forecast-daily-{ATTR_API_FORECAST_PRECIPITATION_PROBABILITY}",
        keys=[
            AOD_TOWN,
            AOD_FORECAST_DAILY,
            AOD_FORECAST_CURRENT,
            AOD_PRECIPITATION_PROBABILITY,
        ],
        name="Daily forecast precipitation probability",
        native_unit_of_measurement=PERCENTAGE,
    ),
    AemetSensorEntityDescription(
        entity_registry_enabled_default=False,
        key=f"forecast-hourly-{ATTR_API_FORECAST_PRECIPITATION_PROBABILITY}",
        keys=[
            AOD_TOWN,
            AOD_FORECAST_HOURLY,
            AOD_FORECAST_CURRENT,
            AOD_PRECIPITATION_PROBABILITY,
        ],
        name="Hourly forecast precipitation probability",
        native_unit_of_measurement=PERCENTAGE,
    ),
    AemetSensorEntityDescription(
        key=f"forecast-daily-{ATTR_API_FORECAST_TEMP}",
        keys=[AOD_TOWN, AOD_FORECAST_DAILY, AOD_FORECAST_CURRENT, AOD_TEMP_MAX],
        name="Daily forecast temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
    AemetSensorEntityDescription(
        key=f"forecast-daily-{ATTR_API_FORECAST_TEMP_LOW}",
        keys=[AOD_TOWN, AOD_FORECAST_DAILY, AOD_FORECAST_CURRENT, AOD_TEMP_MIN],
        name="Daily forecast temperature low",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
    AemetSensorEntityDescription(
        entity_registry_enabled_default=False,
        key=f"forecast-hourly-{ATTR_API_FORECAST_TEMP}",
        keys=[AOD_TOWN, AOD_FORECAST_HOURLY, AOD_FORECAST_CURRENT, AOD_TEMP],
        name="Hourly forecast temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
    AemetSensorEntityDescription(
        key=f"forecast-daily-{ATTR_API_FORECAST_TIME}",
        keys=[AOD_TOWN, AOD_FORECAST_DAILY, AOD_FORECAST_CURRENT, AOD_TIMESTAMP_UTC],
        name="Daily forecast time",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=dt_util.parse_datetime,
    ),
    AemetSensorEntityDescription(
        entity_registry_enabled_default=False,
        key=f"forecast-hourly-{ATTR_API_FORECAST_TIME}",
        keys=[AOD_TOWN, AOD_FORECAST_HOURLY, AOD_FORECAST_CURRENT, AOD_TIMESTAMP_UTC],
        name="Hourly forecast time",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=dt_util.parse_datetime,
    ),
    AemetSensorEntityDescription(
        key=f"forecast-daily-{ATTR_API_FORECAST_WIND_BEARING}",
        keys=[AOD_TOWN, AOD_FORECAST_DAILY, AOD_FORECAST_CURRENT, AOD_WIND_DIRECTION],
        name="Daily forecast wind bearing",
        native_unit_of_measurement=DEGREE,
    ),
    AemetSensorEntityDescription(
        entity_registry_enabled_default=False,
        key=f"forecast-hourly-{ATTR_API_FORECAST_WIND_BEARING}",
        keys=[AOD_TOWN, AOD_FORECAST_HOURLY, AOD_FORECAST_CURRENT, AOD_WIND_DIRECTION],
        name="Hourly forecast wind bearing",
        native_unit_of_measurement=DEGREE,
    ),
    AemetSensorEntityDescription(
        entity_registry_enabled_default=False,
        key=f"forecast-hourly-{ATTR_API_FORECAST_WIND_MAX_SPEED}",
        keys=[AOD_TOWN, AOD_FORECAST_HOURLY, AOD_FORECAST_CURRENT, AOD_WIND_SPEED_MAX],
        name="Hourly forecast wind max speed",
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        device_class=SensorDeviceClass.WIND_SPEED,
    ),
    AemetSensorEntityDescription(
        key=f"forecast-daily-{ATTR_API_FORECAST_WIND_SPEED}",
        keys=[AOD_TOWN, AOD_FORECAST_DAILY, AOD_FORECAST_CURRENT, AOD_WIND_SPEED],
        name="Daily forecast wind speed",
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        device_class=SensorDeviceClass.WIND_SPEED,
    ),
    AemetSensorEntityDescription(
        entity_registry_enabled_default=False,
        key=f"forecast-hourly-{ATTR_API_FORECAST_WIND_SPEED}",
        keys=[AOD_TOWN, AOD_FORECAST_HOURLY, AOD_FORECAST_CURRENT, AOD_WIND_SPEED],
        name="Hourly forecast wind speed",
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        device_class=SensorDeviceClass.WIND_SPEED,
    ),
)


WEATHER_SENSORS: Final[tuple[AemetSensorEntityDescription, ...]] = (
    AemetSensorEntityDescription(
        key=ATTR_API_CONDITION,
        keys=[AOD_WEATHER, AOD_CONDITION],
        name="Condition",
        value_fn=CONDITIONS_MAP.get,
    ),
    AemetSensorEntityDescription(
        key=ATTR_API_HUMIDITY,
        keys=[AOD_WEATHER, AOD_HUMIDITY],
        name="Humidity",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    AemetSensorEntityDescription(
        key=ATTR_API_PRESSURE,
        keys=[AOD_WEATHER, AOD_PRESSURE],
        name="Pressure",
        native_unit_of_measurement=UnitOfPressure.HPA,
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    AemetSensorEntityDescription(
        key=ATTR_API_RAIN,
        keys=[AOD_WEATHER, AOD_RAIN],
        name="Rain",
        native_unit_of_measurement=UnitOfVolumetricFlux.MILLIMETERS_PER_HOUR,
        device_class=SensorDeviceClass.PRECIPITATION_INTENSITY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    AemetSensorEntityDescription(
        key=ATTR_API_RAIN_PROB,
        keys=[AOD_WEATHER, AOD_RAIN_PROBABILITY],
        name="Rain probability",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    AemetSensorEntityDescription(
        key=ATTR_API_SNOW,
        keys=[AOD_WEATHER, AOD_SNOW],
        name="Snow",
        native_unit_of_measurement=UnitOfVolumetricFlux.MILLIMETERS_PER_HOUR,
        device_class=SensorDeviceClass.PRECIPITATION_INTENSITY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    AemetSensorEntityDescription(
        key=ATTR_API_SNOW_PROB,
        keys=[AOD_WEATHER, AOD_SNOW_PROBABILITY],
        name="Snow probability",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    AemetSensorEntityDescription(
        key=ATTR_API_STATION_ID,
        keys=[AOD_STATION, AOD_ID],
        name="Station ID",
    ),
    AemetSensorEntityDescription(
        key=ATTR_API_STATION_NAME,
        keys=[AOD_STATION, AOD_NAME],
        name="Station name",
    ),
    AemetSensorEntityDescription(
        key=ATTR_API_STATION_TIMESTAMP,
        keys=[AOD_STATION, AOD_TIMESTAMP_UTC],
        name="Station timestamp",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=dt_util.parse_datetime,
    ),
    AemetSensorEntityDescription(
        key=ATTR_API_STORM_PROB,
        keys=[AOD_WEATHER, AOD_STORM_PROBABILITY],
        name="Storm probability",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    AemetSensorEntityDescription(
        key=ATTR_API_TEMPERATURE,
        keys=[AOD_WEATHER, AOD_TEMP],
        name="Temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    AemetSensorEntityDescription(
        key=ATTR_API_TEMPERATURE_FEELING,
        keys=[AOD_WEATHER, AOD_FEEL_TEMP],
        name="Temperature feeling",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    AemetSensorEntityDescription(
        key=ATTR_API_TOWN_ID,
        keys=[AOD_TOWN, AOD_ID],
        name="Town ID",
    ),
    AemetSensorEntityDescription(
        key=ATTR_API_TOWN_NAME,
        keys=[AOD_TOWN, AOD_NAME],
        name="Town name",
    ),
    AemetSensorEntityDescription(
        key=ATTR_API_TOWN_TIMESTAMP,
        keys=[AOD_TOWN, AOD_FORECAST_HOURLY, AOD_TIMESTAMP_UTC],
        name="Town timestamp",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=dt_util.parse_datetime,
    ),
    AemetSensorEntityDescription(
        key=ATTR_API_WIND_BEARING,
        keys=[AOD_WEATHER, AOD_WIND_DIRECTION],
        name="Wind bearing",
        native_unit_of_measurement=DEGREE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    AemetSensorEntityDescription(
        key=ATTR_API_WIND_MAX_SPEED,
        keys=[AOD_WEATHER, AOD_WIND_SPEED_MAX],
        name="Wind max speed",
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        device_class=SensorDeviceClass.WIND_SPEED,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    AemetSensorEntityDescription(
        key=ATTR_API_WIND_SPEED,
        keys=[AOD_WEATHER, AOD_WIND_SPEED],
        name="Wind speed",
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        device_class=SensorDeviceClass.WIND_SPEED,
        state_class=SensorStateClass.MEASUREMENT,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: AemetConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up AEMET OpenData sensor entities based on a config entry."""
    domain_data = config_entry.runtime_data
    name = domain_data.name
    coordinator = domain_data.coordinator

    unique_id = config_entry.unique_id
    assert unique_id is not None

    async_add_entities(
        AemetSensor(
            name,
            coordinator,
            description,
            unique_id,
        )
        for description in FORECAST_SENSORS + WEATHER_SENSORS
        if dict_nested_value(coordinator.data["lib"], description.keys) is not None
    )


class AemetSensor(AemetEntity, SensorEntity):
    """Implementation of an AEMET OpenData sensor."""

    entity_description: AemetSensorEntityDescription

    def __init__(
        self,
        name: str,
        coordinator: WeatherUpdateCoordinator,
        description: AemetSensorEntityDescription,
        unique_id: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, name, unique_id)
        self.entity_description = description
        self._attr_unique_id = f"{unique_id}-{description.key}"

    @property
    def native_value(self):
        """Return the state of the device."""
        value = self.get_aemet_value(self.entity_description.keys)
        return self.entity_description.value_fn(value)
