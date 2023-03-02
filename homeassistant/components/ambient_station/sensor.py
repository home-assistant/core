"""Support for Ambient Weather Station sensors."""
from __future__ import annotations

from datetime import datetime

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_NAME,
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONCENTRATION_PARTS_PER_MILLION,
    DEGREE,
    LIGHT_LUX,
    PERCENTAGE,
    UnitOfIrradiance,
    UnitOfPrecipitationDepth,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
    UnitOfVolumetricFlux,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AmbientStation, AmbientWeatherEntity
from .const import ATTR_LAST_DATA, DOMAIN, TYPE_SOLARRADIATION, TYPE_SOLARRADIATION_LX

TYPE_24HOURRAININ = "24hourrainin"
TYPE_AQI_PM25 = "aqi_pm25"
TYPE_AQI_PM25_24H = "aqi_pm25_24h"
TYPE_AQI_PM25_IN = "aqi_pm25_in"
TYPE_AQI_PM25_IN_24H = "aqi_pm25_in_24h"
TYPE_BAROMABSIN = "baromabsin"
TYPE_BAROMRELIN = "baromrelin"
TYPE_CO2 = "co2"
TYPE_DAILYRAININ = "dailyrainin"
TYPE_DEWPOINT = "dewPoint"
TYPE_EVENTRAININ = "eventrainin"
TYPE_FEELSLIKE = "feelsLike"
TYPE_HOURLYRAININ = "hourlyrainin"
TYPE_HUMIDITY = "humidity"
TYPE_HUMIDITY1 = "humidity1"
TYPE_HUMIDITY10 = "humidity10"
TYPE_HUMIDITY2 = "humidity2"
TYPE_HUMIDITY3 = "humidity3"
TYPE_HUMIDITY4 = "humidity4"
TYPE_HUMIDITY5 = "humidity5"
TYPE_HUMIDITY6 = "humidity6"
TYPE_HUMIDITY7 = "humidity7"
TYPE_HUMIDITY8 = "humidity8"
TYPE_HUMIDITY9 = "humidity9"
TYPE_HUMIDITYIN = "humidityin"
TYPE_LASTRAIN = "lastRain"
TYPE_LIGHTNING_PER_DAY = "lightning_day"
TYPE_LIGHTNING_PER_HOUR = "lightning_hour"
TYPE_MAXDAILYGUST = "maxdailygust"
TYPE_MONTHLYRAININ = "monthlyrainin"
TYPE_PM25 = "pm25"
TYPE_PM25_24H = "pm25_24h"
TYPE_PM25_IN = "pm25_in"
TYPE_PM25_IN_24H = "pm25_in_24h"
TYPE_SOILHUM1 = "soilhum1"
TYPE_SOILHUM10 = "soilhum10"
TYPE_SOILHUM2 = "soilhum2"
TYPE_SOILHUM3 = "soilhum3"
TYPE_SOILHUM4 = "soilhum4"
TYPE_SOILHUM5 = "soilhum5"
TYPE_SOILHUM6 = "soilhum6"
TYPE_SOILHUM7 = "soilhum7"
TYPE_SOILHUM8 = "soilhum8"
TYPE_SOILHUM9 = "soilhum9"
TYPE_SOILTEMP1F = "soiltemp1f"
TYPE_SOILTEMP10F = "soiltemp10f"
TYPE_SOILTEMP2F = "soiltemp2f"
TYPE_SOILTEMP3F = "soiltemp3f"
TYPE_SOILTEMP4F = "soiltemp4f"
TYPE_SOILTEMP5F = "soiltemp5f"
TYPE_SOILTEMP6F = "soiltemp6f"
TYPE_SOILTEMP7F = "soiltemp7f"
TYPE_SOILTEMP8F = "soiltemp8f"
TYPE_SOILTEMP9F = "soiltemp9f"
TYPE_TEMP10F = "temp10f"
TYPE_TEMP1F = "temp1f"
TYPE_TEMP2F = "temp2f"
TYPE_TEMP3F = "temp3f"
TYPE_TEMP4F = "temp4f"
TYPE_TEMP5F = "temp5f"
TYPE_TEMP6F = "temp6f"
TYPE_TEMP7F = "temp7f"
TYPE_TEMP8F = "temp8f"
TYPE_TEMP9F = "temp9f"
TYPE_TEMPF = "tempf"
TYPE_TEMPINF = "tempinf"
TYPE_TOTALRAININ = "totalrainin"
TYPE_UV = "uv"
TYPE_WEEKLYRAININ = "weeklyrainin"
TYPE_WINDDIR = "winddir"
TYPE_WINDDIR_AVG10M = "winddir_avg10m"
TYPE_WINDDIR_AVG2M = "winddir_avg2m"
TYPE_WINDGUSTDIR = "windgustdir"
TYPE_WINDGUSTMPH = "windgustmph"
TYPE_WINDSPDMPH_AVG10M = "windspdmph_avg10m"
TYPE_WINDSPDMPH_AVG2M = "windspdmph_avg2m"
TYPE_WINDSPEEDMPH = "windspeedmph"
TYPE_YEARLYRAININ = "yearlyrainin"

SENSOR_DESCRIPTIONS = (
    SensorEntityDescription(
        key=TYPE_24HOURRAININ,
        name="24 hr rain",
        native_unit_of_measurement=UnitOfPrecipitationDepth.INCHES,
        device_class=SensorDeviceClass.PRECIPITATION,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key=TYPE_AQI_PM25,
        name="AQI PM2.5",
        device_class=SensorDeviceClass.AQI,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=TYPE_AQI_PM25_24H,
        name="AQI PM2.5 24h avg",
        device_class=SensorDeviceClass.AQI,
    ),
    SensorEntityDescription(
        key=TYPE_AQI_PM25_IN,
        name="AQI PM2.5 indoor",
        device_class=SensorDeviceClass.AQI,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=TYPE_AQI_PM25_IN_24H,
        name="AQI PM2.5 indoor 24h avg",
        device_class=SensorDeviceClass.AQI,
    ),
    SensorEntityDescription(
        key=TYPE_BAROMABSIN,
        name="Abs pressure",
        native_unit_of_measurement=UnitOfPressure.INHG,
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=TYPE_BAROMRELIN,
        name="Rel pressure",
        native_unit_of_measurement=UnitOfPressure.INHG,
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=TYPE_CO2,
        name="CO2",
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        device_class=SensorDeviceClass.CO2,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=TYPE_DAILYRAININ,
        name="Daily rain",
        native_unit_of_measurement=UnitOfPrecipitationDepth.INCHES,
        device_class=SensorDeviceClass.PRECIPITATION,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key=TYPE_DEWPOINT,
        name="Dew point",
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=TYPE_EVENTRAININ,
        name="Event rain",
        native_unit_of_measurement=UnitOfPrecipitationDepth.INCHES,
        device_class=SensorDeviceClass.PRECIPITATION,
        state_class=SensorStateClass.TOTAL,
    ),
    SensorEntityDescription(
        key=TYPE_FEELSLIKE,
        name="Feels like",
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=TYPE_HOURLYRAININ,
        name="Hourly rain rate",
        native_unit_of_measurement=UnitOfVolumetricFlux.INCHES_PER_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.PRECIPITATION_INTENSITY,
    ),
    SensorEntityDescription(
        key=TYPE_HUMIDITY10,
        name="Humidity 10",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=TYPE_HUMIDITY1,
        name="Humidity 1",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=TYPE_HUMIDITY2,
        name="Humidity 2",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=TYPE_HUMIDITY3,
        name="Humidity 3",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=TYPE_HUMIDITY4,
        name="Humidity 4",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=TYPE_HUMIDITY5,
        name="Humidity 5",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=TYPE_HUMIDITY6,
        name="Humidity 6",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=TYPE_HUMIDITY7,
        name="Humidity 7",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=TYPE_HUMIDITY8,
        name="Humidity 8",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=TYPE_HUMIDITY9,
        name="Humidity 9",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=TYPE_HUMIDITY,
        name="Humidity",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=TYPE_HUMIDITYIN,
        name="Humidity in",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=TYPE_LASTRAIN,
        name="Last rain",
        icon="mdi:water",
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    SensorEntityDescription(
        key=TYPE_LIGHTNING_PER_DAY,
        name="Lightning strikes per day",
        icon="mdi:lightning-bolt",
        native_unit_of_measurement="strikes",
        state_class=SensorStateClass.TOTAL,
    ),
    SensorEntityDescription(
        key=TYPE_LIGHTNING_PER_HOUR,
        name="Lightning strikes per hour",
        icon="mdi:lightning-bolt",
        native_unit_of_measurement="strikes",
        state_class=SensorStateClass.TOTAL,
    ),
    SensorEntityDescription(
        key=TYPE_MAXDAILYGUST,
        name="Max gust",
        native_unit_of_measurement=UnitOfSpeed.MILES_PER_HOUR,
        device_class=SensorDeviceClass.WIND_SPEED,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=TYPE_MONTHLYRAININ,
        name="Monthly rain",
        native_unit_of_measurement=UnitOfPrecipitationDepth.INCHES,
        device_class=SensorDeviceClass.PRECIPITATION,
        state_class=SensorStateClass.TOTAL,
    ),
    SensorEntityDescription(
        key=TYPE_PM25_24H,
        name="PM25 24h avg",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        device_class=SensorDeviceClass.PM25,
    ),
    SensorEntityDescription(
        key=TYPE_PM25_IN,
        name="PM25 indoor",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        device_class=SensorDeviceClass.PM25,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=TYPE_PM25_IN_24H,
        name="PM25 indoor 24h avg",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        device_class=SensorDeviceClass.PM25,
    ),
    SensorEntityDescription(
        key=TYPE_PM25,
        name="PM25",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        device_class=SensorDeviceClass.PM25,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=TYPE_SOILHUM10,
        name="Soil humidity 10",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=TYPE_SOILHUM1,
        name="Soil humidity 1",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=TYPE_SOILHUM2,
        name="Soil humidity 2",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=TYPE_SOILHUM3,
        name="Soil humidity 3",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=TYPE_SOILHUM4,
        name="Soil humidity 4",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=TYPE_SOILHUM5,
        name="Soil humidity 5",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=TYPE_SOILHUM6,
        name="Soil humidity 6",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=TYPE_SOILHUM7,
        name="Soil humidity 7",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=TYPE_SOILHUM8,
        name="Soil humidity 8",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=TYPE_SOILHUM9,
        name="Soil humidity 9",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=TYPE_SOILTEMP10F,
        name="Soil temp 10",
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=TYPE_SOILTEMP1F,
        name="Soil temp 1",
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=TYPE_SOILTEMP2F,
        name="Soil temp 2",
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=TYPE_SOILTEMP3F,
        name="Soil temp 3",
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=TYPE_SOILTEMP4F,
        name="Soil temp 4",
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=TYPE_SOILTEMP5F,
        name="Soil temp 5",
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=TYPE_SOILTEMP6F,
        name="Soil temp 6",
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=TYPE_SOILTEMP7F,
        name="Soil temp 7",
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=TYPE_SOILTEMP8F,
        name="Soil temp 8",
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=TYPE_SOILTEMP9F,
        name="Soil temp 9",
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=TYPE_SOLARRADIATION,
        name="Solar rad",
        native_unit_of_measurement=UnitOfIrradiance.WATTS_PER_SQUARE_METER,
        device_class=SensorDeviceClass.IRRADIANCE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=TYPE_SOLARRADIATION_LX,
        name="Solar rad",
        native_unit_of_measurement=LIGHT_LUX,
        device_class=SensorDeviceClass.ILLUMINANCE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=TYPE_TEMP10F,
        name="Temp 10",
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=TYPE_TEMP1F,
        name="Temp 1",
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=TYPE_TEMP2F,
        name="Temp 2",
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=TYPE_TEMP3F,
        name="Temp 3",
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=TYPE_TEMP4F,
        name="Temp 4",
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=TYPE_TEMP5F,
        name="Temp 5",
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=TYPE_TEMP6F,
        name="Temp 6",
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=TYPE_TEMP7F,
        name="Temp 7",
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=TYPE_TEMP8F,
        name="Temp 8",
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=TYPE_TEMP9F,
        name="Temp 9",
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=TYPE_TEMPF,
        name="Temp",
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=TYPE_TEMPINF,
        name="Inside temp",
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=TYPE_TOTALRAININ,
        name="Lifetime rain",
        native_unit_of_measurement=UnitOfPrecipitationDepth.INCHES,
        device_class=SensorDeviceClass.PRECIPITATION,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key=TYPE_UV,
        name="UV index",
        native_unit_of_measurement="Index",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=TYPE_WEEKLYRAININ,
        name="Weekly rain",
        native_unit_of_measurement=UnitOfPrecipitationDepth.INCHES,
        device_class=SensorDeviceClass.PRECIPITATION,
        state_class=SensorStateClass.TOTAL,
    ),
    SensorEntityDescription(
        key=TYPE_WINDDIR,
        name="Wind dir",
        icon="mdi:weather-windy",
        native_unit_of_measurement=DEGREE,
    ),
    SensorEntityDescription(
        key=TYPE_WINDDIR_AVG10M,
        name="Wind dir avg 10m",
        icon="mdi:weather-windy",
        native_unit_of_measurement=DEGREE,
    ),
    SensorEntityDescription(
        key=TYPE_WINDDIR_AVG2M,
        name="Wind dir avg 2m",
        icon="mdi:weather-windy",
        native_unit_of_measurement=DEGREE,
    ),
    SensorEntityDescription(
        key=TYPE_WINDGUSTDIR,
        name="Gust dir",
        icon="mdi:weather-windy",
        native_unit_of_measurement=DEGREE,
    ),
    SensorEntityDescription(
        key=TYPE_WINDGUSTMPH,
        name="Wind gust",
        native_unit_of_measurement=UnitOfSpeed.MILES_PER_HOUR,
        device_class=SensorDeviceClass.WIND_SPEED,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=TYPE_WINDSPDMPH_AVG10M,
        name="Wind avg 10m",
        native_unit_of_measurement=UnitOfSpeed.MILES_PER_HOUR,
        device_class=SensorDeviceClass.WIND_SPEED,
    ),
    SensorEntityDescription(
        key=TYPE_WINDSPDMPH_AVG2M,
        name="Wind avg 2m",
        native_unit_of_measurement=UnitOfSpeed.MILES_PER_HOUR,
        device_class=SensorDeviceClass.WIND_SPEED,
    ),
    SensorEntityDescription(
        key=TYPE_WINDSPEEDMPH,
        name="Wind speed",
        native_unit_of_measurement=UnitOfSpeed.MILES_PER_HOUR,
        device_class=SensorDeviceClass.WIND_SPEED,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=TYPE_YEARLYRAININ,
        name="Yearly rain",
        native_unit_of_measurement=UnitOfPrecipitationDepth.INCHES,
        device_class=SensorDeviceClass.PRECIPITATION,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Ambient PWS sensors based on a config entry."""
    ambient = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        AmbientWeatherSensor(ambient, mac_address, station[ATTR_NAME], description)
        for mac_address, station in ambient.stations.items()
        for description in SENSOR_DESCRIPTIONS
        if description.key in station[ATTR_LAST_DATA]
    )


class AmbientWeatherSensor(AmbientWeatherEntity, SensorEntity):
    """Define an Ambient sensor."""

    def __init__(
        self,
        ambient: AmbientStation,
        mac_address: str,
        station_name: str,
        description: EntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(ambient, mac_address, station_name, description)

        if description.key == TYPE_SOLARRADIATION_LX:
            # Since TYPE_SOLARRADIATION and TYPE_SOLARRADIATION_LX will have the same
            # name in the UI, we influence the entity ID of TYPE_SOLARRADIATION_LX here
            # to differentiate them:
            self.entity_id = f"sensor.{station_name}_solar_rad_lx"

    @callback
    def update_from_latest_data(self) -> None:
        """Fetch new state data for the sensor."""
        raw = self._ambient.stations[self._mac_address][ATTR_LAST_DATA][
            self.entity_description.key
        ]

        if self.entity_description.key == TYPE_LASTRAIN:
            self._attr_native_value = datetime.strptime(raw, "%Y-%m-%dT%H:%M:%S.%f%z")
        else:
            self._attr_native_value = raw
