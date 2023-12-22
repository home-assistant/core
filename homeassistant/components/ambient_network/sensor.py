"""Support for Ambient Weather Network sensors."""
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any, cast

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONCENTRATION_PARTS_PER_MILLION,
    DEGREE,
    PERCENTAGE,
    UnitOfIrradiance,
    UnitOfLength,
    UnitOfPrecipitationDepth,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
    UnitOfVolumetricFlux,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .climate_utils import ClimateUtils
from .const import DOMAIN, ENTITY_MNEMONIC
from .coordinator import AmbientNetworkDataUpdateCoordinator
from .entity import AmbientNetworkEntity
from .reducers import Reducers

TYPE_AQI_PM25 = "aqi_pm25"
TYPE_AQI_PM25_24H = "aqi_pm25_24h"
TYPE_BAROMABSIN = "baromabsin"
TYPE_BAROMRELIN = "baromrelin"
TYPE_CO2 = "co2"
TYPE_DAILYRAININ = "dailyrainin"
TYPE_DEWPOINT = "dewPoint"
TYPE_EVENTRAININ = "eventrainin"
TYPE_FEELSLIKE = "feelsLike"
TYPE_HOURLYRAININ = "hourlyrainin"
TYPE_HUMIDITY = "humidity"
TYPE_LASTRAIN = "lastRain"
TYPE_LIGHTNING_DISTANCE = "lightning_distance"
TYPE_LIGHTNING_PER_DAY = "lightning_day"
TYPE_LIGHTNING_PER_HOUR = "lightning_hour"
TYPE_MAXDAILYGUST = "maxdailygust"
TYPE_MONTHLYRAININ = "monthlyrainin"
TYPE_PM25 = "pm25"
TYPE_PM25_24H = "pm25_24h"
TYPE_SOLARRADIATION = "solarradiation"
TYPE_TEMPF = "tempf"
TYPE_UV = "uv"
TYPE_WEEKLYRAININ = "weeklyrainin"
TYPE_WINDDIR = "winddir"
TYPE_WINDGUSTMPH = "windgustmph"
TYPE_WINDSPEEDMPH = "windspeedmph"
TYPE_YEARLYRAININ = "yearlyrainin"


class AmbientNetworkSensorEntityDescription(
    SensorEntityDescription, frozen_or_thawed=True
):
    """An extended class that adds a reducer field."""

    reducer: Callable[[list[Any]], Any] | None = Reducers.mean


SENSOR_DESCRIPTIONS = (
    AmbientNetworkSensorEntityDescription(
        key=TYPE_AQI_PM25,
        translation_key="pm25_aqi",
        device_class=SensorDeviceClass.AQI,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        reducer=Reducers.mean,
    ),
    AmbientNetworkSensorEntityDescription(
        key=TYPE_AQI_PM25_24H,
        translation_key="pm25_aqi_24h_average",
        device_class=SensorDeviceClass.AQI,
        suggested_display_precision=0,
        reducer=Reducers.mean,
    ),
    AmbientNetworkSensorEntityDescription(
        key=TYPE_BAROMABSIN,
        translation_key="absolute_pressure",
        native_unit_of_measurement=UnitOfPressure.INHG,
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        reducer=Reducers.mean,
    ),
    AmbientNetworkSensorEntityDescription(
        key=TYPE_BAROMRELIN,
        translation_key="relative_pressure",
        native_unit_of_measurement=UnitOfPressure.INHG,
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        reducer=Reducers.mean,
    ),
    AmbientNetworkSensorEntityDescription(
        key=TYPE_CO2,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        device_class=SensorDeviceClass.CO2,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        reducer=Reducers.mean,
    ),
    AmbientNetworkSensorEntityDescription(
        key=TYPE_DAILYRAININ,
        translation_key="daily_rain",
        native_unit_of_measurement=UnitOfPrecipitationDepth.INCHES,
        device_class=SensorDeviceClass.PRECIPITATION,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
        reducer=Reducers.mean,
    ),
    AmbientNetworkSensorEntityDescription(
        key=TYPE_DEWPOINT,
        translation_key="dew_point",
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        reducer=Reducers.mean,
    ),
    AmbientNetworkSensorEntityDescription(
        key=TYPE_FEELSLIKE,
        translation_key="feels_like",
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        reducer=Reducers.mean,
    ),
    AmbientNetworkSensorEntityDescription(
        key=TYPE_HOURLYRAININ,
        native_unit_of_measurement=UnitOfVolumetricFlux.INCHES_PER_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.PRECIPITATION_INTENSITY,
        suggested_display_precision=2,
        reducer=Reducers.mean,
    ),
    AmbientNetworkSensorEntityDescription(
        key=TYPE_HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        reducer=Reducers.mean,
    ),
    AmbientNetworkSensorEntityDescription(
        key=TYPE_LASTRAIN,
        translation_key="last_rain",
        icon="mdi:water",
        device_class=SensorDeviceClass.TIMESTAMP,
        reducer=Reducers.max,
    ),
    AmbientNetworkSensorEntityDescription(
        key=TYPE_LIGHTNING_PER_DAY,
        translation_key="lightning_strikes_per_day",
        icon="mdi:lightning-bolt",
        native_unit_of_measurement="strikes",
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=0,
        reducer=Reducers.max,
    ),
    AmbientNetworkSensorEntityDescription(
        key=TYPE_LIGHTNING_PER_HOUR,
        translation_key="lightning_strikes_per_hour",
        icon="mdi:lightning-bolt",
        native_unit_of_measurement="strikes",
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=0,
        reducer=Reducers.max,
    ),
    AmbientNetworkSensorEntityDescription(
        key=TYPE_LIGHTNING_DISTANCE,
        translation_key="lightning_distance",
        icon="mdi:lightning-bolt",
        native_unit_of_measurement=UnitOfLength.MILES,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        reducer=Reducers.mean,
    ),
    AmbientNetworkSensorEntityDescription(
        key=TYPE_MAXDAILYGUST,
        translation_key="max_gust",
        native_unit_of_measurement=UnitOfSpeed.MILES_PER_HOUR,
        device_class=SensorDeviceClass.WIND_SPEED,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        reducer=Reducers.max,
    ),
    AmbientNetworkSensorEntityDescription(
        key=TYPE_MONTHLYRAININ,
        translation_key="monthly_rain",
        native_unit_of_measurement=UnitOfPrecipitationDepth.INCHES,
        device_class=SensorDeviceClass.PRECIPITATION,
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=2,
        reducer=Reducers.mean,
    ),
    AmbientNetworkSensorEntityDescription(
        key=TYPE_PM25_24H,
        translation_key="pm25_24h_average",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        device_class=SensorDeviceClass.PM25,
        suggested_display_precision=1,
        reducer=Reducers.mean,
    ),
    AmbientNetworkSensorEntityDescription(
        key=TYPE_PM25,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        device_class=SensorDeviceClass.PM25,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        reducer=Reducers.mean,
    ),
    AmbientNetworkSensorEntityDescription(
        key=TYPE_SOLARRADIATION,
        native_unit_of_measurement=UnitOfIrradiance.WATTS_PER_SQUARE_METER,
        device_class=SensorDeviceClass.IRRADIANCE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        reducer=Reducers.mean,
    ),
    AmbientNetworkSensorEntityDescription(
        key=TYPE_TEMPF,
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        reducer=Reducers.mean,
    ),
    AmbientNetworkSensorEntityDescription(
        key=TYPE_UV,
        translation_key="uv_index",
        native_unit_of_measurement="Index",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        reducer=Reducers.mean,
    ),
    AmbientNetworkSensorEntityDescription(
        key=TYPE_WEEKLYRAININ,
        translation_key="weekly_rain",
        native_unit_of_measurement=UnitOfPrecipitationDepth.INCHES,
        device_class=SensorDeviceClass.PRECIPITATION,
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=2,
        reducer=Reducers.mean,
    ),
    AmbientNetworkSensorEntityDescription(
        key=TYPE_WINDDIR,
        translation_key="wind_direction",
        icon="mdi:weather-windy",
        native_unit_of_measurement=DEGREE,
        suggested_display_precision=0,
        reducer=Reducers.mean,
    ),
    AmbientNetworkSensorEntityDescription(
        key=TYPE_WINDGUSTMPH,
        translation_key="wind_gust",
        native_unit_of_measurement=UnitOfSpeed.MILES_PER_HOUR,
        device_class=SensorDeviceClass.WIND_SPEED,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        reducer=Reducers.max,
    ),
    AmbientNetworkSensorEntityDescription(
        key=TYPE_WINDSPEEDMPH,
        native_unit_of_measurement=UnitOfSpeed.MILES_PER_HOUR,
        device_class=SensorDeviceClass.WIND_SPEED,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        reducer=Reducers.mean,
    ),
    AmbientNetworkSensorEntityDescription(
        key=TYPE_YEARLYRAININ,
        translation_key="yearly_rain",
        native_unit_of_measurement=UnitOfPrecipitationDepth.INCHES,
        device_class=SensorDeviceClass.PRECIPITATION,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
        reducer=Reducers.mean,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Ambient Network sensor platform."""

    coordinator: AmbientNetworkDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    if coordinator.config_entry is not None:
        entities: list[AmbientNetworkSensor] = []
        for description in SENSOR_DESCRIPTIONS:
            # Check whether any of the stations report this sensor value.
            for station_data in coordinator.data.values():
                sensor_keys: list[str]
                if description.key == TYPE_FEELSLIKE:
                    # Feels like is calculated from temperature, relative humidity, and
                    # wind speed.
                    sensor_keys = [TYPE_TEMPF, TYPE_HUMIDITY, TYPE_WINDSPEEDMPH]

                elif description.key == TYPE_DEWPOINT:
                    # Dew point is calculated from temperature and relative humidity.
                    sensor_keys = [TYPE_TEMPF, TYPE_HUMIDITY]

                else:
                    # Everything else is calculated from the reported value directly.
                    sensor_keys = [description.key]
                if all(
                    AmbientNetworkSensor.get_sensor_value(station_data, key) is not None
                    for key in sensor_keys
                ):
                    entities.append(
                        AmbientNetworkSensor(
                            coordinator,
                            description,
                            coordinator.config_entry.data[ENTITY_MNEMONIC],
                        )
                    )
                    break
        async_add_entities(entities)


class AmbientNetworkSensor(AmbientNetworkEntity, SensorEntity):
    """A sensor implementation for an Ambient Weather Network sensor."""

    def __init__(
        self,
        coordinator: AmbientNetworkDataUpdateCoordinator,
        description: AmbientNetworkSensorEntityDescription,
        mnemonic: str,
    ) -> None:
        """Initialize a sensor object."""

        super().__init__(coordinator, description, mnemonic)
        # Override the entity_id to make them cleaner (otherwise Homeassistant
        # will name them _precipitation_1, _precipitation_2, etc.)
        self.entity_id = f"sensor.{self._device_id.lower()}_{description.key}"
        self._attr_suggested_display_precision = description.suggested_display_precision

    def _calc_attrs(self, key: str) -> Any:
        """Calculate sensor attributes."""

        values: list[Any] = []
        # Fetch the sensor values from all the stations in the virtual station
        for station_data in self.coordinator.data.values():
            value = AmbientNetworkSensor.get_sensor_value(station_data, key)
            if value is not None:
                values.append(value)

        if len(values) > 0:
            # Reduce the list of values into a single value using the specified
            # reducer function.
            reducer = cast(
                AmbientNetworkSensorEntityDescription, self.entity_description
            ).reducer
            if reducer is None:
                return None  # pragma: no cover
            value = reducer(values)
            # Treatments for special units.
            if self.device_class == SensorDeviceClass.TIMESTAMP:
                return datetime.fromtimestamp(
                    value / 1000, tz=dt_util.DEFAULT_TIME_ZONE
                )
            return value

    def _update_attrs(self) -> None:
        """Update sensor attributes."""

        if self.entity_description.key == TYPE_FEELSLIKE:
            # Feels like temperature is a virtual sensor that is calculated from
            # temperature, humdidity, and windspeed.
            self._attr_native_value = ClimateUtils.feels_like_fahrenheit(
                self._calc_attrs(TYPE_TEMPF),
                self._calc_attrs(TYPE_HUMIDITY),
                self._calc_attrs(TYPE_WINDSPEEDMPH),
            )
        elif self.entity_description.key == TYPE_DEWPOINT:
            # Dew point temperature is a virtual sensor that is calculated from
            # temperature and humidity.
            self._attr_native_value = ClimateUtils.dew_point_fahrenheit(
                self._calc_attrs(TYPE_TEMPF), self._calc_attrs(TYPE_HUMIDITY)
            )
        else:
            self._attr_native_value = self._calc_attrs(self.entity_description.key)

    @staticmethod
    def get_sensor_value(station_data: dict[str, Any], sensor_key: str) -> Any | None:
        """Return the sensor value from a station if available.

        Eliminates data from stations that haven't been updated for a while.
        """

        if "lastData" not in station_data:
            return None  # pragma: no cover

        last_data = station_data["lastData"]
        if "created_at" not in last_data:
            return None  # pragma: no cover

        # Eliminate data that has been generated more than an hour ago. The station is
        # probably offline.
        created_at = last_data["created_at"]
        if int(created_at / 1000) < int(
            (datetime.now() - timedelta(hours=1)).timestamp()
        ):
            return None  # pragma: no cover

        if sensor_key not in last_data:
            return None

        return last_data[sensor_key]
