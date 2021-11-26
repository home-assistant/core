"""Support for Ambient Weather Station sensors."""
from __future__ import annotations

from datetime import datetime

from homeassistant.components.sensor import (
    STATE_CLASS_MEASUREMENT,
    STATE_CLASS_TOTAL_INCREASING,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_NAME,
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONCENTRATION_PARTS_PER_MILLION,
    DEGREE,
    DEVICE_CLASS_CO2,
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_ILLUMINANCE,
    DEVICE_CLASS_PM25,
    DEVICE_CLASS_PRESSURE,
    DEVICE_CLASS_TEMPERATURE,
    DEVICE_CLASS_TIMESTAMP,
    IRRADIATION_WATTS_PER_SQUARE_METER,
    LIGHT_LUX,
    PERCENTAGE,
    PRECIPITATION_INCHES,
    PRECIPITATION_INCHES_PER_HOUR,
    PRESSURE_INHG,
    SPEED_MILES_PER_HOUR,
    TEMP_FAHRENHEIT,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import (
    TYPE_SOLARRADIATION,
    TYPE_SOLARRADIATION_LX,
    AmbientStation,
    AmbientWeatherEntity,
)
from .const import ATTR_LAST_DATA, DOMAIN

TYPE_24HOURRAININ = "24hourrainin"
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
        name="24 Hr Rain",
        icon="mdi:water",
        native_unit_of_measurement=PRECIPITATION_INCHES,
        state_class=STATE_CLASS_TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key=TYPE_BAROMABSIN,
        name="Abs Pressure",
        native_unit_of_measurement=PRESSURE_INHG,
        device_class=DEVICE_CLASS_PRESSURE,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key=TYPE_BAROMRELIN,
        name="Rel Pressure",
        native_unit_of_measurement=PRESSURE_INHG,
        device_class=DEVICE_CLASS_PRESSURE,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key=TYPE_CO2,
        name="co2",
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        device_class=DEVICE_CLASS_CO2,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key=TYPE_DAILYRAININ,
        name="Daily Rain",
        icon="mdi:water",
        native_unit_of_measurement=PRECIPITATION_INCHES,
        state_class=STATE_CLASS_TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key=TYPE_DEWPOINT,
        name="Dew Point",
        native_unit_of_measurement=TEMP_FAHRENHEIT,
        device_class=DEVICE_CLASS_TEMPERATURE,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key=TYPE_EVENTRAININ,
        name="Event Rain",
        icon="mdi:water",
        native_unit_of_measurement=PRECIPITATION_INCHES,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key=TYPE_FEELSLIKE,
        name="Feels Like",
        native_unit_of_measurement=TEMP_FAHRENHEIT,
        device_class=DEVICE_CLASS_TEMPERATURE,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key=TYPE_HOURLYRAININ,
        name="Hourly Rain Rate",
        icon="mdi:water",
        native_unit_of_measurement=PRECIPITATION_INCHES_PER_HOUR,
        state_class=STATE_CLASS_TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key=TYPE_HUMIDITY10,
        name="Humidity 10",
        native_unit_of_measurement=PERCENTAGE,
        device_class=DEVICE_CLASS_HUMIDITY,
    ),
    SensorEntityDescription(
        key=TYPE_HUMIDITY1,
        name="Humidity 1",
        native_unit_of_measurement=PERCENTAGE,
        device_class=DEVICE_CLASS_HUMIDITY,
    ),
    SensorEntityDescription(
        key=TYPE_HUMIDITY2,
        name="Humidity 2",
        native_unit_of_measurement=PERCENTAGE,
        device_class=DEVICE_CLASS_HUMIDITY,
    ),
    SensorEntityDescription(
        key=TYPE_HUMIDITY3,
        name="Humidity 3",
        native_unit_of_measurement=PERCENTAGE,
        device_class=DEVICE_CLASS_HUMIDITY,
    ),
    SensorEntityDescription(
        key=TYPE_HUMIDITY4,
        name="Humidity 4",
        native_unit_of_measurement=PERCENTAGE,
        device_class=DEVICE_CLASS_HUMIDITY,
    ),
    SensorEntityDescription(
        key=TYPE_HUMIDITY5,
        name="Humidity 5",
        native_unit_of_measurement=PERCENTAGE,
        device_class=DEVICE_CLASS_HUMIDITY,
    ),
    SensorEntityDescription(
        key=TYPE_HUMIDITY6,
        name="Humidity 6",
        native_unit_of_measurement=PERCENTAGE,
        device_class=DEVICE_CLASS_HUMIDITY,
    ),
    SensorEntityDescription(
        key=TYPE_HUMIDITY7,
        name="Humidity 7",
        native_unit_of_measurement=PERCENTAGE,
        device_class=DEVICE_CLASS_HUMIDITY,
    ),
    SensorEntityDescription(
        key=TYPE_HUMIDITY8,
        name="Humidity 8",
        native_unit_of_measurement=PERCENTAGE,
        device_class=DEVICE_CLASS_HUMIDITY,
    ),
    SensorEntityDescription(
        key=TYPE_HUMIDITY9,
        name="Humidity 9",
        native_unit_of_measurement=PERCENTAGE,
        device_class=DEVICE_CLASS_HUMIDITY,
    ),
    SensorEntityDescription(
        key=TYPE_HUMIDITY,
        name="Humidity",
        native_unit_of_measurement=PERCENTAGE,
        device_class=DEVICE_CLASS_HUMIDITY,
    ),
    SensorEntityDescription(
        key=TYPE_HUMIDITYIN,
        name="Humidity In",
        native_unit_of_measurement=PERCENTAGE,
        device_class=DEVICE_CLASS_HUMIDITY,
    ),
    SensorEntityDescription(
        key=TYPE_LASTRAIN,
        name="Last Rain",
        icon="mdi:water",
        device_class=DEVICE_CLASS_TIMESTAMP,
    ),
    SensorEntityDescription(
        key=TYPE_MAXDAILYGUST,
        name="Max Gust",
        icon="mdi:weather-windy",
        native_unit_of_measurement=SPEED_MILES_PER_HOUR,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key=TYPE_MONTHLYRAININ,
        name="Monthly Rain",
        icon="mdi:water",
        native_unit_of_measurement=PRECIPITATION_INCHES,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key=TYPE_PM25_24H,
        name="PM25 24h Avg",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        device_class=DEVICE_CLASS_PM25,
    ),
    SensorEntityDescription(
        key=TYPE_PM25_IN,
        name="PM25 Indoor",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        device_class=DEVICE_CLASS_PM25,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key=TYPE_PM25_IN_24H,
        name="PM25 Indoor 24h Avg",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        device_class=DEVICE_CLASS_PM25,
    ),
    SensorEntityDescription(
        key=TYPE_PM25,
        name="PM25",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        device_class=DEVICE_CLASS_PM25,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key=TYPE_SOILHUM10,
        name="Soil Humidity 10",
        native_unit_of_measurement=PERCENTAGE,
        device_class=DEVICE_CLASS_HUMIDITY,
    ),
    SensorEntityDescription(
        key=TYPE_SOILHUM1,
        name="Soil Humidity 1",
        native_unit_of_measurement=PERCENTAGE,
        device_class=DEVICE_CLASS_HUMIDITY,
    ),
    SensorEntityDescription(
        key=TYPE_SOILHUM2,
        name="Soil Humidity 2",
        native_unit_of_measurement=PERCENTAGE,
        device_class=DEVICE_CLASS_HUMIDITY,
    ),
    SensorEntityDescription(
        key=TYPE_SOILHUM3,
        name="Soil Humidity 3",
        native_unit_of_measurement=PERCENTAGE,
        device_class=DEVICE_CLASS_HUMIDITY,
    ),
    SensorEntityDescription(
        key=TYPE_SOILHUM4,
        name="Soil Humidity 4",
        native_unit_of_measurement=PERCENTAGE,
        device_class=DEVICE_CLASS_HUMIDITY,
    ),
    SensorEntityDescription(
        key=TYPE_SOILHUM5,
        name="Soil Humidity 5",
        native_unit_of_measurement=PERCENTAGE,
        device_class=DEVICE_CLASS_HUMIDITY,
    ),
    SensorEntityDescription(
        key=TYPE_SOILHUM6,
        name="Soil Humidity 6",
        native_unit_of_measurement=PERCENTAGE,
        device_class=DEVICE_CLASS_HUMIDITY,
    ),
    SensorEntityDescription(
        key=TYPE_SOILHUM7,
        name="Soil Humidity 7",
        native_unit_of_measurement=PERCENTAGE,
        device_class=DEVICE_CLASS_HUMIDITY,
    ),
    SensorEntityDescription(
        key=TYPE_SOILHUM8,
        name="Soil Humidity 8",
        native_unit_of_measurement=PERCENTAGE,
        device_class=DEVICE_CLASS_HUMIDITY,
    ),
    SensorEntityDescription(
        key=TYPE_SOILHUM9,
        name="Soil Humidity 9",
        native_unit_of_measurement=PERCENTAGE,
        device_class=DEVICE_CLASS_HUMIDITY,
    ),
    SensorEntityDescription(
        key=TYPE_SOILTEMP10F,
        name="Soil Temp 10",
        native_unit_of_measurement=TEMP_FAHRENHEIT,
        device_class=DEVICE_CLASS_TEMPERATURE,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key=TYPE_SOILTEMP1F,
        name="Soil Temp 1",
        native_unit_of_measurement=TEMP_FAHRENHEIT,
        device_class=DEVICE_CLASS_TEMPERATURE,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key=TYPE_SOILTEMP2F,
        name="Soil Temp 2",
        native_unit_of_measurement=TEMP_FAHRENHEIT,
        device_class=DEVICE_CLASS_TEMPERATURE,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key=TYPE_SOILTEMP3F,
        name="Soil Temp 3",
        native_unit_of_measurement=TEMP_FAHRENHEIT,
        device_class=DEVICE_CLASS_TEMPERATURE,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key=TYPE_SOILTEMP4F,
        name="Soil Temp 4",
        native_unit_of_measurement=TEMP_FAHRENHEIT,
        device_class=DEVICE_CLASS_TEMPERATURE,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key=TYPE_SOILTEMP5F,
        name="Soil Temp 5",
        native_unit_of_measurement=TEMP_FAHRENHEIT,
        device_class=DEVICE_CLASS_TEMPERATURE,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key=TYPE_SOILTEMP6F,
        name="Soil Temp 6",
        native_unit_of_measurement=TEMP_FAHRENHEIT,
        device_class=DEVICE_CLASS_TEMPERATURE,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key=TYPE_SOILTEMP7F,
        name="Soil Temp 7",
        native_unit_of_measurement=TEMP_FAHRENHEIT,
        device_class=DEVICE_CLASS_TEMPERATURE,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key=TYPE_SOILTEMP8F,
        name="Soil Temp 8",
        native_unit_of_measurement=TEMP_FAHRENHEIT,
        device_class=DEVICE_CLASS_TEMPERATURE,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key=TYPE_SOILTEMP9F,
        name="Soil Temp 9",
        native_unit_of_measurement=TEMP_FAHRENHEIT,
        device_class=DEVICE_CLASS_TEMPERATURE,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key=TYPE_SOLARRADIATION,
        name="Solar Rad",
        native_unit_of_measurement=IRRADIATION_WATTS_PER_SQUARE_METER,
        device_class=DEVICE_CLASS_ILLUMINANCE,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key=TYPE_SOLARRADIATION_LX,
        name="Solar Rad",
        native_unit_of_measurement=LIGHT_LUX,
        device_class=DEVICE_CLASS_ILLUMINANCE,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key=TYPE_TEMP10F,
        name="Temp 10",
        native_unit_of_measurement=TEMP_FAHRENHEIT,
        device_class=DEVICE_CLASS_TEMPERATURE,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key=TYPE_TEMP1F,
        name="Temp 1",
        native_unit_of_measurement=TEMP_FAHRENHEIT,
        device_class=DEVICE_CLASS_TEMPERATURE,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key=TYPE_TEMP2F,
        name="Temp 2",
        native_unit_of_measurement=TEMP_FAHRENHEIT,
        device_class=DEVICE_CLASS_TEMPERATURE,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key=TYPE_TEMP3F,
        name="Temp 3",
        native_unit_of_measurement=TEMP_FAHRENHEIT,
        device_class=DEVICE_CLASS_TEMPERATURE,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key=TYPE_TEMP4F,
        name="Temp 4",
        native_unit_of_measurement=TEMP_FAHRENHEIT,
        device_class=DEVICE_CLASS_TEMPERATURE,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key=TYPE_TEMP5F,
        name="Temp 5",
        native_unit_of_measurement=TEMP_FAHRENHEIT,
        device_class=DEVICE_CLASS_TEMPERATURE,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key=TYPE_TEMP6F,
        name="Temp 6",
        native_unit_of_measurement=TEMP_FAHRENHEIT,
        device_class=DEVICE_CLASS_TEMPERATURE,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key=TYPE_TEMP7F,
        name="Temp 7",
        native_unit_of_measurement=TEMP_FAHRENHEIT,
        device_class=DEVICE_CLASS_TEMPERATURE,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key=TYPE_TEMP8F,
        name="Temp 8",
        native_unit_of_measurement=TEMP_FAHRENHEIT,
        device_class=DEVICE_CLASS_TEMPERATURE,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key=TYPE_TEMP9F,
        name="Temp 9",
        native_unit_of_measurement=TEMP_FAHRENHEIT,
        device_class=DEVICE_CLASS_TEMPERATURE,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key=TYPE_TEMPF,
        name="Temp",
        native_unit_of_measurement=TEMP_FAHRENHEIT,
        device_class=DEVICE_CLASS_TEMPERATURE,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key=TYPE_TEMPINF,
        name="Inside Temp",
        native_unit_of_measurement=TEMP_FAHRENHEIT,
        device_class=DEVICE_CLASS_TEMPERATURE,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key=TYPE_TOTALRAININ,
        name="Lifetime Rain",
        icon="mdi:water",
        native_unit_of_measurement=PRECIPITATION_INCHES,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key=TYPE_UV,
        name="UV Index",
        native_unit_of_measurement="Index",
        device_class=DEVICE_CLASS_ILLUMINANCE,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key=TYPE_WEEKLYRAININ,
        name="Weekly Rain",
        icon="mdi:water",
        native_unit_of_measurement=PRECIPITATION_INCHES,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key=TYPE_WINDDIR,
        name="Wind Dir",
        icon="mdi:weather-windy",
        native_unit_of_measurement=DEGREE,
    ),
    SensorEntityDescription(
        key=TYPE_WINDDIR_AVG10M,
        name="Wind Dir Avg 10m",
        icon="mdi:weather-windy",
        native_unit_of_measurement=DEGREE,
    ),
    SensorEntityDescription(
        key=TYPE_WINDDIR_AVG2M,
        name="Wind Dir Avg 2m",
        icon="mdi:weather-windy",
        native_unit_of_measurement=DEGREE,
    ),
    SensorEntityDescription(
        key=TYPE_WINDGUSTDIR,
        name="Gust Dir",
        icon="mdi:weather-windy",
        native_unit_of_measurement=DEGREE,
    ),
    SensorEntityDescription(
        key=TYPE_WINDGUSTMPH,
        name="Wind Gust",
        icon="mdi:weather-windy",
        native_unit_of_measurement=SPEED_MILES_PER_HOUR,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key=TYPE_WINDSPDMPH_AVG10M,
        name="Wind Avg 10m",
        icon="mdi:weather-windy",
        native_unit_of_measurement=SPEED_MILES_PER_HOUR,
    ),
    SensorEntityDescription(
        key=TYPE_WINDSPDMPH_AVG2M,
        name="Wind Avg 2m",
        icon="mdi:weather-windy",
        native_unit_of_measurement=SPEED_MILES_PER_HOUR,
    ),
    SensorEntityDescription(
        key=TYPE_WINDSPEEDMPH,
        name="Wind Speed",
        icon="mdi:weather-windy",
        native_unit_of_measurement=SPEED_MILES_PER_HOUR,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key=TYPE_YEARLYRAININ,
        name="Yearly Rain",
        icon="mdi:water",
        native_unit_of_measurement=PRECIPITATION_INCHES,
        state_class=STATE_CLASS_TOTAL_INCREASING,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Ambient PWS sensors based on a config entry."""
    ambient = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        [
            AmbientWeatherSensor(ambient, mac_address, station[ATTR_NAME], description)
            for mac_address, station in ambient.stations.items()
            for description in SENSOR_DESCRIPTIONS
            if description.key in station[ATTR_LAST_DATA]
        ]
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
