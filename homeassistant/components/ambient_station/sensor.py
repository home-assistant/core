"""Support for Ambient Weather Station sensors."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
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
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import TYPE_SOLARRADIATION, TYPE_SOLARRADIATION_LX, AmbientWeatherEntity
from .const import (
    ATTR_LAST_DATA,
    DATA_CLIENT,
    DOMAIN,
    TYPE_24HOURRAININ,
    TYPE_BAROMABSIN,
    TYPE_BAROMRELIN,
    TYPE_CO2,
    TYPE_DAILYRAININ,
    TYPE_DEWPOINT,
    TYPE_EVENTRAININ,
    TYPE_FEELSLIKE,
    TYPE_HOURLYRAININ,
    TYPE_HUMIDITY,
    TYPE_HUMIDITY1,
    TYPE_HUMIDITY2,
    TYPE_HUMIDITY3,
    TYPE_HUMIDITY4,
    TYPE_HUMIDITY5,
    TYPE_HUMIDITY6,
    TYPE_HUMIDITY7,
    TYPE_HUMIDITY8,
    TYPE_HUMIDITY9,
    TYPE_HUMIDITY10,
    TYPE_HUMIDITYIN,
    TYPE_LASTRAIN,
    TYPE_MAXDAILYGUST,
    TYPE_MONTHLYRAININ,
    TYPE_PM25,
    TYPE_PM25_24H,
    TYPE_PM25_IN,
    TYPE_PM25_IN_24H,
    TYPE_SOILHUM1,
    TYPE_SOILHUM2,
    TYPE_SOILHUM3,
    TYPE_SOILHUM4,
    TYPE_SOILHUM5,
    TYPE_SOILHUM6,
    TYPE_SOILHUM7,
    TYPE_SOILHUM8,
    TYPE_SOILHUM9,
    TYPE_SOILHUM10,
    TYPE_SOILTEMP1F,
    TYPE_SOILTEMP2F,
    TYPE_SOILTEMP3F,
    TYPE_SOILTEMP4F,
    TYPE_SOILTEMP5F,
    TYPE_SOILTEMP6F,
    TYPE_SOILTEMP7F,
    TYPE_SOILTEMP8F,
    TYPE_SOILTEMP9F,
    TYPE_SOILTEMP10F,
    TYPE_TEMP1F,
    TYPE_TEMP2F,
    TYPE_TEMP3F,
    TYPE_TEMP4F,
    TYPE_TEMP5F,
    TYPE_TEMP6F,
    TYPE_TEMP7F,
    TYPE_TEMP8F,
    TYPE_TEMP9F,
    TYPE_TEMP10F,
    TYPE_TEMPF,
    TYPE_TEMPINF,
    TYPE_TOTALRAININ,
    TYPE_UV,
    TYPE_WEEKLYRAININ,
    TYPE_WINDDIR,
    TYPE_WINDDIR_AVG2M,
    TYPE_WINDDIR_AVG10M,
    TYPE_WINDGUSTDIR,
    TYPE_WINDGUSTMPH,
    TYPE_WINDSPDMPH_AVG2M,
    TYPE_WINDSPDMPH_AVG10M,
    TYPE_WINDSPEEDMPH,
    TYPE_YEARLYRAININ,
)

SENSOR_DESCRIPTIONS = (
    SensorEntityDescription(
        key=TYPE_24HOURRAININ,
        name="24 Hr Rain",
        icon="mdi:water",
        native_unit_of_measurement=PRECIPITATION_INCHES,
    ),
    SensorEntityDescription(
        key=TYPE_BAROMABSIN,
        name="Abs Pressure",
        native_unit_of_measurement=PRESSURE_INHG,
        device_class=DEVICE_CLASS_PRESSURE,
    ),
    SensorEntityDescription(
        key=TYPE_BAROMRELIN,
        name="Rel Pressure",
        native_unit_of_measurement=PRESSURE_INHG,
        device_class=DEVICE_CLASS_PRESSURE,
    ),
    SensorEntityDescription(
        key=TYPE_CO2,
        name="co2",
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        device_class=DEVICE_CLASS_CO2,
    ),
    SensorEntityDescription(
        key=TYPE_DAILYRAININ,
        name="Daily Rain",
        icon="mdi:water",
        native_unit_of_measurement=PRECIPITATION_INCHES,
    ),
    SensorEntityDescription(
        key=TYPE_DEWPOINT,
        name="Dew Point",
        native_unit_of_measurement=TEMP_FAHRENHEIT,
        device_class=DEVICE_CLASS_TEMPERATURE,
    ),
    SensorEntityDescription(
        key=TYPE_EVENTRAININ,
        name="Event Rain",
        icon="mdi:water",
        native_unit_of_measurement=PRECIPITATION_INCHES,
    ),
    SensorEntityDescription(
        key=TYPE_FEELSLIKE,
        name="Feels Like",
        native_unit_of_measurement=TEMP_FAHRENHEIT,
        device_class=DEVICE_CLASS_TEMPERATURE,
    ),
    SensorEntityDescription(
        key=TYPE_HOURLYRAININ,
        name="Hourly Rain Rate",
        icon="mdi:water",
        native_unit_of_measurement=PRECIPITATION_INCHES_PER_HOUR,
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
    ),
    SensorEntityDescription(
        key=TYPE_MONTHLYRAININ,
        name="Monthly Rain",
        icon="mdi:water",
        native_unit_of_measurement=PRECIPITATION_INCHES,
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
    ),
    SensorEntityDescription(
        key=TYPE_SOILTEMP1F,
        name="Soil Temp 1",
        native_unit_of_measurement=TEMP_FAHRENHEIT,
        device_class=DEVICE_CLASS_TEMPERATURE,
    ),
    SensorEntityDescription(
        key=TYPE_SOILTEMP2F,
        name="Soil Temp 2",
        native_unit_of_measurement=TEMP_FAHRENHEIT,
        device_class=DEVICE_CLASS_TEMPERATURE,
    ),
    SensorEntityDescription(
        key=TYPE_SOILTEMP3F,
        name="Soil Temp 3",
        native_unit_of_measurement=TEMP_FAHRENHEIT,
        device_class=DEVICE_CLASS_TEMPERATURE,
    ),
    SensorEntityDescription(
        key=TYPE_SOILTEMP4F,
        name="Soil Temp 4",
        native_unit_of_measurement=TEMP_FAHRENHEIT,
        device_class=DEVICE_CLASS_TEMPERATURE,
    ),
    SensorEntityDescription(
        key=TYPE_SOILTEMP5F,
        name="Soil Temp 5",
        native_unit_of_measurement=TEMP_FAHRENHEIT,
        device_class=DEVICE_CLASS_TEMPERATURE,
    ),
    SensorEntityDescription(
        key=TYPE_SOILTEMP6F,
        name="Soil Temp 6",
        native_unit_of_measurement=TEMP_FAHRENHEIT,
        device_class=DEVICE_CLASS_TEMPERATURE,
    ),
    SensorEntityDescription(
        key=TYPE_SOILTEMP7F,
        name="Soil Temp 7",
        native_unit_of_measurement=TEMP_FAHRENHEIT,
        device_class=DEVICE_CLASS_TEMPERATURE,
    ),
    SensorEntityDescription(
        key=TYPE_SOILTEMP8F,
        name="Soil Temp 8",
        native_unit_of_measurement=TEMP_FAHRENHEIT,
        device_class=DEVICE_CLASS_TEMPERATURE,
    ),
    SensorEntityDescription(
        key=TYPE_SOILTEMP9F,
        name="Soil Temp 9",
        native_unit_of_measurement=TEMP_FAHRENHEIT,
        device_class=DEVICE_CLASS_TEMPERATURE,
    ),
    SensorEntityDescription(
        key=TYPE_SOLARRADIATION,
        name="Solar Rad",
        native_unit_of_measurement=IRRADIATION_WATTS_PER_SQUARE_METER,
        device_class=DEVICE_CLASS_ILLUMINANCE,
    ),
    SensorEntityDescription(
        key=TYPE_SOLARRADIATION_LX,
        name="Solar Rad (lx)",
        native_unit_of_measurement=LIGHT_LUX,
        device_class=DEVICE_CLASS_ILLUMINANCE,
    ),
    SensorEntityDescription(
        key=TYPE_TEMP10F,
        name="Temp 10",
        native_unit_of_measurement=TEMP_FAHRENHEIT,
        device_class=DEVICE_CLASS_TEMPERATURE,
    ),
    SensorEntityDescription(
        key=TYPE_TEMP1F,
        name="Temp 1",
        native_unit_of_measurement=TEMP_FAHRENHEIT,
        device_class=DEVICE_CLASS_TEMPERATURE,
    ),
    SensorEntityDescription(
        key=TYPE_TEMP2F,
        name="Temp 2",
        native_unit_of_measurement=TEMP_FAHRENHEIT,
        device_class=DEVICE_CLASS_TEMPERATURE,
    ),
    SensorEntityDescription(
        key=TYPE_TEMP3F,
        name="Temp 3",
        native_unit_of_measurement=TEMP_FAHRENHEIT,
        device_class=DEVICE_CLASS_TEMPERATURE,
    ),
    SensorEntityDescription(
        key=TYPE_TEMP4F,
        name="Temp 4",
        native_unit_of_measurement=TEMP_FAHRENHEIT,
        device_class=DEVICE_CLASS_TEMPERATURE,
    ),
    SensorEntityDescription(
        key=TYPE_TEMP5F,
        name="Temp 5",
        native_unit_of_measurement=TEMP_FAHRENHEIT,
        device_class=DEVICE_CLASS_TEMPERATURE,
    ),
    SensorEntityDescription(
        key=TYPE_TEMP6F,
        name="Temp 6",
        native_unit_of_measurement=TEMP_FAHRENHEIT,
        device_class=DEVICE_CLASS_TEMPERATURE,
    ),
    SensorEntityDescription(
        key=TYPE_TEMP7F,
        name="Temp 7",
        native_unit_of_measurement=TEMP_FAHRENHEIT,
        device_class=DEVICE_CLASS_TEMPERATURE,
    ),
    SensorEntityDescription(
        key=TYPE_TEMP8F,
        name="Temp 8",
        native_unit_of_measurement=TEMP_FAHRENHEIT,
        device_class=DEVICE_CLASS_TEMPERATURE,
    ),
    SensorEntityDescription(
        key=TYPE_TEMP9F,
        name="Temp 9",
        native_unit_of_measurement=TEMP_FAHRENHEIT,
        device_class=DEVICE_CLASS_TEMPERATURE,
    ),
    SensorEntityDescription(
        key=TYPE_TEMPF,
        name="Temp",
        native_unit_of_measurement=TEMP_FAHRENHEIT,
        device_class=DEVICE_CLASS_TEMPERATURE,
    ),
    SensorEntityDescription(
        key=TYPE_TEMPINF,
        name="Inside Temp",
        native_unit_of_measurement=TEMP_FAHRENHEIT,
        device_class=DEVICE_CLASS_TEMPERATURE,
    ),
    SensorEntityDescription(
        key=TYPE_TOTALRAININ,
        name="Lifetime Rain",
        icon="mdi:water",
        native_unit_of_measurement=PRECIPITATION_INCHES,
    ),
    SensorEntityDescription(
        key=TYPE_UV,
        name="uv",
        native_unit_of_measurement="Index",
        device_class=DEVICE_CLASS_ILLUMINANCE,
    ),
    SensorEntityDescription(
        key=TYPE_WEEKLYRAININ,
        name="Weekly Rain",
        icon="mdi:water",
        native_unit_of_measurement=PRECIPITATION_INCHES,
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
        native_unit_of_measurement=SPEED_MILES_PER_HOUR,
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
    ),
    SensorEntityDescription(
        key=TYPE_YEARLYRAININ,
        name="Yearly Rain",
        icon="mdi:water",
        native_unit_of_measurement=PRECIPITATION_INCHES,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Ambient PWS sensors based on a config entry."""
    ambient = hass.data[DOMAIN][DATA_CLIENT][entry.entry_id]

    async_add_entities(
        [
            AmbientWeatherSensor(ambient, mac_address, station[ATTR_NAME], description)
            for description in SENSOR_DESCRIPTIONS
            for mac_address, station in ambient.stations.items()
            if description.key in station[ATTR_LAST_DATA]
        ]
    )


class AmbientWeatherSensor(AmbientWeatherEntity, SensorEntity):
    """Define an Ambient sensor."""

    @callback
    def update_from_latest_data(self) -> None:
        """Fetch new state data for the sensor."""
        self._attr_native_value = self._ambient.stations[self._mac_address][
            ATTR_LAST_DATA
        ].get(self.entity_description.key)
