"""Platform for sensor integration."""
from dataclasses import dataclass
import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONCENTRATION_PARTS_PER_MILLION,
    DEGREE,
    PERCENTAGE,
    UnitOfIrradiance,
    UnitOfLength,
    UnitOfPrecipitationDepth,
    UnitOfPressure,
    UnitOfSpeed,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

# from homeassistant.helpers.entity import EntityDescription
from .const import (
    CONF_IP,
    DEVICE_NAME,
    DOMAIN,
    LEAF_BATT,
    LEAF_DATA,
    LEAK_BATT,
    LEAK_DATA,
    MAIN_DATA,
    PM25_BATT,
    PM25_DATA,
    SOIL_BATT,
    SOIL_DATA,
    TEMP_BATT,
    TEMP_DATA,
    TEMPHUMI_BATT,
    TEMPHUMI_DATA,
)
from .coordinator import WittiotDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

TYPE_TEMPINF = "tempinf"
TYPE_HUMIDITYIN = "humidityin"
TYPE_REL = "baromrelin"
TYPE_ABS = "baromabsin"
TYPE_TEMPOUT = "tempf"
TYPE_HUMIOUT = "humidity"
TYPE_WDIR = "winddir"
TYPE_WS = "windspeedmph"
TYPE_WG = "windgustmph"
TYPE_SR = "solarradiation"
TYPE_UV = "uv"
TYPE_DWM = "daywindmax"
TYPE_FEELLIKE = "feellike"
TYPE_DEWP = "dewpoint"
TYPE_RR = "rainratein"
TYPE_ER = "eventrainin"
TYPE_DR = "dailyrainin"
TYPE_WR = "weeklyrainin"
TYPE_MR = "monthlyrainin"
TYPE_YR = "yearlyrainin"
TYPE_PIEZO_RR = "rrain_piezo"
TYPE_PIEZO_ER = "erain_piezo"
TYPE_PIEZO_DR = "drain_piezo"
TYPE_PIEZO_WR = "wrain_piezo"
TYPE_PIEZO_MR = "mrain_piezo"
TYPE_PIEZO_YR = "yrain_piezo"
TYPE_PM25CH1 = "pm25_ch1"
TYPE_PM25CH2 = "pm25_ch2"
TYPE_PM25CH3 = "pm25_ch3"
TYPE_PM25CH4 = "pm25_ch4"
TYPE_PM25RTAQICH1 = "pm25_aqi_ch1"
TYPE_PM25RTAQICH2 = "pm25_aqi_ch2"
TYPE_PM25RTAQICH3 = "pm25_aqi_ch3"
TYPE_PM25RTAQICH4 = "pm25_aqi_ch4"
TYPE_PM2524HAQICH1 = "pm25_avg_24h_ch1"
TYPE_PM2524HAQICH2 = "pm25_avg_24h_ch2"
TYPE_PM2524HAQICH3 = "pm25_avg_24h_ch3"
TYPE_PM2524HAQICH4 = "pm25_avg_24h_ch4"
TYPE_CO2IN = "co2in"
TYPE_CO224HIN = "co2in_24h"
TYPE_CO2OUT = "co2"
TYPE_CO224HOUT = "co2_24h"
TYPE_CO2PM25 = "pm25_co2"
TYPE_CO224HPM25 = "pm25_24h_co2"
TYPE_CO2PM10 = "pm10_co2"
TYPE_CO224HPM10 = "pm10_24h_co2"
TYPE_CO2RTPM10 = "pm10_aqi_co2"
TYPE_CO2RTPM25 = "pm25_aqi_co2"
TYPE_CO2TEMP = "tf_co2"
TYPE_CO2HUMI = "humi_co2"
TYPE_LIGHTNING = "lightning"
TYPE_LIGHTNINGTIME = "lightning_time"
TYPE_LIGHTNINGNUM = "lightning_num"
TYPE_LEAKCH1 = "leak_ch1"
TYPE_LEAKCH2 = "leak_ch2"
TYPE_LEAKCH3 = "leak_ch3"
TYPE_LEAKCH4 = "leak_ch4"
TYPE_TEMPCH1 = "temp_ch1"
TYPE_TEMPCH2 = "temp_ch2"
TYPE_TEMPCH3 = "temp_ch3"
TYPE_TEMPCH4 = "temp_ch4"
TYPE_TEMPCH5 = "temp_ch5"
TYPE_TEMPCH6 = "temp_ch6"
TYPE_TEMPCH7 = "temp_ch7"
TYPE_TEMPCH8 = "temp_ch8"
TYPE_HUMICH1 = "humidity_ch1"
TYPE_HUMICH2 = "humidity_ch2"
TYPE_HUMICH3 = "humidity_ch3"
TYPE_HUMICH4 = "humidity_ch4"
TYPE_HUMICH5 = "humidity_ch5"
TYPE_HUMICH6 = "humidity_ch6"
TYPE_HUMICH7 = "humidity_ch7"
TYPE_HUMICH8 = "humidity_ch8"
TYPE_SOILCH1 = "Soilmoisture_ch1"
TYPE_SOILCH2 = "Soilmoisture_ch2"
TYPE_SOILCH3 = "Soilmoisture_ch3"
TYPE_SOILCH4 = "Soilmoisture_ch4"
TYPE_SOILCH5 = "Soilmoisture_ch5"
TYPE_SOILCH6 = "Soilmoisture_ch6"
TYPE_SOILCH7 = "Soilmoisture_ch7"
TYPE_SOILCH8 = "Soilmoisture_ch8"
TYPE_ONLYTEMPCH1 = "tf_ch1"
TYPE_ONLYTEMPCH2 = "tf_ch2"
TYPE_ONLYTEMPCH3 = "tf_ch3"
TYPE_ONLYTEMPCH4 = "tf_ch4"
TYPE_ONLYTEMPCH5 = "tf_ch5"
TYPE_ONLYTEMPCH6 = "tf_ch6"
TYPE_ONLYTEMPCH7 = "tf_ch7"
TYPE_ONLYTEMPCH8 = "tf_ch8"
TYPE_LEAFCH1 = "leaf_ch1"
TYPE_LEAFCH2 = "leaf_ch2"
TYPE_LEAFCH3 = "leaf_ch3"
TYPE_LEAFCH4 = "leaf_ch4"
TYPE_LEAFCH5 = "leaf_ch5"
TYPE_LEAFCH6 = "leaf_ch6"
TYPE_LEAFCH7 = "leaf_ch7"
TYPE_LEAFCH8 = "leaf_ch8"

TYPE_PM25CH1_BATT = "pm25_ch1_batt"
TYPE_PM25CH2_BATT = "pm25_ch2_batt"
TYPE_PM25CH3_BATT = "pm25_ch3_batt"
TYPE_PM25CH4_BATT = "pm25_ch4_batt"
TYPE_LEAKCH1_BATT = "leak_ch1_batt"
TYPE_LEAKCH2_BATT = "leak_ch2_batt"
TYPE_LEAKCH3_BATT = "leak_ch3_batt"
TYPE_LEAKCH4_BATT = "leak_ch4_batt"
TYPE_TEMPCH1_BATT = "temph_ch1_batt"
TYPE_TEMPCH2_BATT = "temph_ch2_batt"
TYPE_TEMPCH3_BATT = "temph_ch3_batt"
TYPE_TEMPCH4_BATT = "temph_ch4_batt"
TYPE_TEMPCH5_BATT = "temph_ch5_batt"
TYPE_TEMPCH6_BATT = "temph_ch6_batt"
TYPE_TEMPCH7_BATT = "temph_ch7_batt"
TYPE_TEMPCH8_BATT = "temph_ch8_batt"
TYPE_SOILCH1_BATT = "Soilmoisture_ch1_batt"
TYPE_SOILCH2_BATT = "Soilmoisture_ch2_batt"
TYPE_SOILCH3_BATT = "Soilmoisture_ch3_batt"
TYPE_SOILCH4_BATT = "Soilmoisture_ch4_batt"
TYPE_SOILCH5_BATT = "Soilmoisture_ch5_batt"
TYPE_SOILCH6_BATT = "Soilmoisture_ch6_batt"
TYPE_SOILCH7_BATT = "Soilmoisture_ch7_batt"
TYPE_SOILCH8_BATT = "Soilmoisture_ch8_batt"
TYPE_ONLYTEMPCH1_BATT = "tf_ch1_batt"
TYPE_ONLYTEMPCH2_BATT = "tf_ch2_batt"
TYPE_ONLYTEMPCH3_BATT = "tf_ch3_batt"
TYPE_ONLYTEMPCH4_BATT = "tf_ch4_batt"
TYPE_ONLYTEMPCH5_BATT = "tf_ch5_batt"
TYPE_ONLYTEMPCH6_BATT = "tf_ch6_batt"
TYPE_ONLYTEMPCH7_BATT = "tf_ch7_batt"
TYPE_ONLYTEMPCH8_BATT = "tf_ch8_batt"
TYPE_LEAFCH1_BATT = "leaf_ch1_batt"
TYPE_LEAFCH2_BATT = "leaf_ch2_batt"
TYPE_LEAFCH3_BATT = "leaf_ch3_batt"
TYPE_LEAFCH4_BATT = "leaf_ch4_batt"
TYPE_LEAFCH5_BATT = "leaf_ch5_batt"
TYPE_LEAFCH6_BATT = "leaf_ch6_batt"
TYPE_LEAFCH7_BATT = "leaf_ch7_batt"
TYPE_LEAFCH8_BATT = "leaf_ch8_batt"


@dataclass(frozen=True, kw_only=True)
class WittiotSensorEntityDescription(SensorEntityDescription):
    """Class describing WittIOT sensor entities."""

    sensor_type: str = ""


SENSOR_DESCRIPTIONS = (
    WittiotSensorEntityDescription(
        key=TYPE_TEMPINF,
        sensor_type=MAIN_DATA,
        name="Indoor Temp",
        native_unit_of_measurement="°F",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WittiotSensorEntityDescription(
        key=TYPE_TEMPOUT,
        sensor_type=MAIN_DATA,
        name="Outdoor Temp",
        native_unit_of_measurement="°F",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WittiotSensorEntityDescription(
        key=TYPE_FEELLIKE,
        sensor_type=MAIN_DATA,
        name="Feel Like",
        native_unit_of_measurement="°F",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WittiotSensorEntityDescription(
        key=TYPE_DEWP,
        name="Dew Point",
        sensor_type=MAIN_DATA,
        native_unit_of_measurement="°F",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WittiotSensorEntityDescription(
        key=TYPE_CO2TEMP,
        sensor_type=MAIN_DATA,
        name="CO2 Temp",
        native_unit_of_measurement="°F",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WittiotSensorEntityDescription(
        key=TYPE_HUMIDITYIN,
        sensor_type=MAIN_DATA,
        name="Indoor Humidity",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
    ),
    WittiotSensorEntityDescription(
        key=TYPE_HUMIOUT,
        sensor_type=MAIN_DATA,
        name="Outdoor Humidity",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
    ),
    WittiotSensorEntityDescription(
        key=TYPE_CO2HUMI,
        sensor_type=MAIN_DATA,
        name="CO2 Humidity",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
    ),
    WittiotSensorEntityDescription(
        key=TYPE_REL,
        sensor_type=MAIN_DATA,
        name="Relative",
        native_unit_of_measurement=UnitOfPressure.INHG,
        device_class=SensorDeviceClass.PRESSURE,
    ),
    WittiotSensorEntityDescription(
        key=TYPE_ABS,
        sensor_type=MAIN_DATA,
        name="Absolute",
        native_unit_of_measurement=UnitOfPressure.INHG,
        device_class=SensorDeviceClass.PRESSURE,
    ),
    WittiotSensorEntityDescription(
        key=TYPE_WDIR,
        sensor_type=MAIN_DATA,
        name="Wind Direction",
        icon="mdi:weather-windy",
        native_unit_of_measurement=DEGREE,
    ),
    WittiotSensorEntityDescription(
        key=TYPE_WS,
        sensor_type=MAIN_DATA,
        name="Wind Speed",
        icon="mdi:weather-windy",
        native_unit_of_measurement=UnitOfSpeed.MILES_PER_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WittiotSensorEntityDescription(
        key=TYPE_WG,
        sensor_type=MAIN_DATA,
        name="Wind Gust",
        icon="mdi:weather-windy",
        native_unit_of_measurement=UnitOfSpeed.MILES_PER_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WittiotSensorEntityDescription(
        key=TYPE_DWM,
        sensor_type=MAIN_DATA,
        name="Day Wind Max",
        icon="mdi:weather-windy",
        native_unit_of_measurement=UnitOfSpeed.MILES_PER_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WittiotSensorEntityDescription(
        key=TYPE_UV,
        sensor_type=MAIN_DATA,
        name="UV-Index",
        native_unit_of_measurement="Index",
        device_class=SensorDeviceClass.ILLUMINANCE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WittiotSensorEntityDescription(
        key=TYPE_SR,
        sensor_type=MAIN_DATA,
        name="Solar Irradiance",
        native_unit_of_measurement=UnitOfIrradiance.WATTS_PER_SQUARE_METER,
        device_class=SensorDeviceClass.ILLUMINANCE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WittiotSensorEntityDescription(
        key=TYPE_RR,
        sensor_type=MAIN_DATA,
        name="Rain Rate",
        icon="mdi:water",
        native_unit_of_measurement=UnitOfPrecipitationDepth.INCHES,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WittiotSensorEntityDescription(
        key=TYPE_ER,
        sensor_type=MAIN_DATA,
        name="Rain Event",
        icon="mdi:water",
        native_unit_of_measurement=UnitOfPrecipitationDepth.INCHES,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WittiotSensorEntityDescription(
        key=TYPE_DR,
        sensor_type=MAIN_DATA,
        name="Rain Day",
        icon="mdi:water",
        native_unit_of_measurement=UnitOfPrecipitationDepth.INCHES,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WittiotSensorEntityDescription(
        key=TYPE_WR,
        sensor_type=MAIN_DATA,
        name="Rain Week",
        icon="mdi:water",
        native_unit_of_measurement=UnitOfPrecipitationDepth.INCHES,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WittiotSensorEntityDescription(
        key=TYPE_MR,
        sensor_type=MAIN_DATA,
        name="Rain Month",
        icon="mdi:water",
        native_unit_of_measurement=UnitOfPrecipitationDepth.INCHES,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WittiotSensorEntityDescription(
        key=TYPE_YR,
        sensor_type=MAIN_DATA,
        name="Rain Year",
        icon="mdi:water",
        native_unit_of_measurement=UnitOfPrecipitationDepth.INCHES,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WittiotSensorEntityDescription(
        key=TYPE_PIEZO_RR,
        sensor_type=MAIN_DATA,
        name="Piezo Rain Rate",
        icon="mdi:water",
        native_unit_of_measurement=UnitOfPrecipitationDepth.INCHES,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WittiotSensorEntityDescription(
        key=TYPE_PIEZO_ER,
        sensor_type=MAIN_DATA,
        name="Piezo Rain Event",
        icon="mdi:water",
        native_unit_of_measurement=UnitOfPrecipitationDepth.INCHES,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WittiotSensorEntityDescription(
        key=TYPE_PIEZO_DR,
        sensor_type=MAIN_DATA,
        name="Piezo Rain Day",
        icon="mdi:water",
        native_unit_of_measurement=UnitOfPrecipitationDepth.INCHES,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WittiotSensorEntityDescription(
        key=TYPE_PIEZO_WR,
        sensor_type=MAIN_DATA,
        name="Piezo Rain Week",
        icon="mdi:water",
        native_unit_of_measurement=UnitOfPrecipitationDepth.INCHES,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WittiotSensorEntityDescription(
        key=TYPE_PIEZO_MR,
        sensor_type=MAIN_DATA,
        name="Piezo Rain Month",
        icon="mdi:water",
        native_unit_of_measurement=UnitOfPrecipitationDepth.INCHES,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WittiotSensorEntityDescription(
        key=TYPE_PIEZO_YR,
        sensor_type=MAIN_DATA,
        name="Piezo Rain Year",
        icon="mdi:water",
        native_unit_of_measurement=UnitOfPrecipitationDepth.INCHES,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WittiotSensorEntityDescription(
        key=TYPE_CO2IN,
        sensor_type=MAIN_DATA,
        name="Indoor CO2",
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        device_class=SensorDeviceClass.CO2,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WittiotSensorEntityDescription(
        key=TYPE_CO2OUT,
        sensor_type=MAIN_DATA,
        name="CO2",
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        device_class=SensorDeviceClass.CO2,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WittiotSensorEntityDescription(
        key=TYPE_CO224HIN,
        sensor_type=MAIN_DATA,
        name="Indoor 24H CO2",
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        device_class=SensorDeviceClass.CO2,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WittiotSensorEntityDescription(
        key=TYPE_CO224HOUT,
        sensor_type=MAIN_DATA,
        name="24H CO2",
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        device_class=SensorDeviceClass.CO2,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WittiotSensorEntityDescription(
        key=TYPE_CO2PM25,
        sensor_type=MAIN_DATA,
        name="CO2 PM2.5",
        device_class=SensorDeviceClass.PM25,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WittiotSensorEntityDescription(
        key=TYPE_CO2RTPM25,
        sensor_type=MAIN_DATA,
        name="CO2 PM2.5 AQI",
        device_class=SensorDeviceClass.AQI,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WittiotSensorEntityDescription(
        key=TYPE_CO224HPM25,
        sensor_type=MAIN_DATA,
        name="CO2 24H PM2.5 AQI",
        device_class=SensorDeviceClass.AQI,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WittiotSensorEntityDescription(
        key=TYPE_CO2PM10,
        sensor_type=MAIN_DATA,
        name="CO2 PM10",
        device_class=SensorDeviceClass.PM10,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WittiotSensorEntityDescription(
        key=TYPE_CO2RTPM10,
        sensor_type=MAIN_DATA,
        name="CO2 PM10 AQI",
        device_class=SensorDeviceClass.AQI,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WittiotSensorEntityDescription(
        key=TYPE_CO224HPM10,
        sensor_type=MAIN_DATA,
        name="CO2 24H PM10 AQI",
        device_class=SensorDeviceClass.AQI,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WittiotSensorEntityDescription(
        key=TYPE_LIGHTNING,
        sensor_type=MAIN_DATA,
        name="Thunder Last Distamce",
        icon="mdi:lightning-bolt",
        native_unit_of_measurement=UnitOfLength.MILES,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WittiotSensorEntityDescription(
        key=TYPE_LIGHTNINGTIME,
        sensor_type=MAIN_DATA,
        name="Thunder Last Timestamp",
        icon="mdi:lightning-bolt",
    ),
    WittiotSensorEntityDescription(
        key=TYPE_LIGHTNINGNUM,
        sensor_type=MAIN_DATA,
        name="Thunder Daily Count",
        icon="mdi:lightning-bolt",
        state_class=SensorStateClass.TOTAL,
    ),
    WittiotSensorEntityDescription(
        key=TYPE_PM25CH1,
        sensor_type=PM25_DATA,
        name="CH1 PM2.5",
        device_class=SensorDeviceClass.PM25,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WittiotSensorEntityDescription(
        key=TYPE_PM25CH2,
        sensor_type=PM25_DATA,
        name="CH2 PM2.5",
        device_class=SensorDeviceClass.PM25,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WittiotSensorEntityDescription(
        key=TYPE_PM25CH3,
        sensor_type=PM25_DATA,
        name="CH3 PM2.5",
        device_class=SensorDeviceClass.PM25,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WittiotSensorEntityDescription(
        key=TYPE_PM25CH4,
        sensor_type=PM25_DATA,
        name="CH4 PM2.5",
        device_class=SensorDeviceClass.PM25,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WittiotSensorEntityDescription(
        key=TYPE_PM25RTAQICH1,
        sensor_type=PM25_DATA,
        name="CH1 PM2.5 AQI",
        device_class=SensorDeviceClass.AQI,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WittiotSensorEntityDescription(
        key=TYPE_PM25RTAQICH2,
        sensor_type=PM25_DATA,
        name="CH2 PM2.5 AQI",
        device_class=SensorDeviceClass.AQI,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WittiotSensorEntityDescription(
        key=TYPE_PM25RTAQICH3,
        sensor_type=PM25_DATA,
        name="CH3 PM2.5 AQI",
        device_class=SensorDeviceClass.AQI,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WittiotSensorEntityDescription(
        key=TYPE_PM25RTAQICH4,
        sensor_type=PM25_DATA,
        name="CH4 PM2.5 AQI",
        device_class=SensorDeviceClass.AQI,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WittiotSensorEntityDescription(
        key=TYPE_PM2524HAQICH1,
        sensor_type=PM25_DATA,
        name="CH1 PM2.5 24H AQI",
        device_class=SensorDeviceClass.AQI,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WittiotSensorEntityDescription(
        key=TYPE_PM2524HAQICH2,
        sensor_type=PM25_DATA,
        name="CH2 PM2.5 24H AQI",
        device_class=SensorDeviceClass.AQI,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WittiotSensorEntityDescription(
        key=TYPE_PM2524HAQICH3,
        sensor_type=PM25_DATA,
        name="CH3 PM2.5 24H AQI",
        device_class=SensorDeviceClass.AQI,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WittiotSensorEntityDescription(
        key=TYPE_PM2524HAQICH4,
        sensor_type=PM25_DATA,
        name="CH4 PM2.5 24H AQI",
        device_class=SensorDeviceClass.AQI,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WittiotSensorEntityDescription(
        key=TYPE_PM25CH1_BATT,
        sensor_type=PM25_BATT,
        name="CH1 PM2.5 Battery",
        icon="mdi:battery",
    ),
    WittiotSensorEntityDescription(
        key=TYPE_PM25CH2_BATT,
        sensor_type=PM25_BATT,
        name="CH2 PM2.5 Battery",
        icon="mdi:battery",
    ),
    WittiotSensorEntityDescription(
        key=TYPE_PM25CH3_BATT,
        sensor_type=PM25_BATT,
        name="CH3 PM2.5 Battery",
        icon="mdi:battery",
    ),
    WittiotSensorEntityDescription(
        key=TYPE_PM25CH4_BATT,
        sensor_type=PM25_BATT,
        name="CH4 PM2.5 Battery",
        icon="mdi:battery",
    ),
    WittiotSensorEntityDescription(
        key=TYPE_LEAKCH1,
        sensor_type=LEAK_DATA,
        name="CH1 Leak",
        icon="mdi:water-alert",
    ),
    WittiotSensorEntityDescription(
        key=TYPE_LEAKCH2,
        sensor_type=LEAK_DATA,
        name="CH2 Leak",
        icon="mdi:water-alert",
    ),
    WittiotSensorEntityDescription(
        key=TYPE_LEAKCH3,
        sensor_type=LEAK_DATA,
        name="CH3 Leak",
        icon="mdi:water-alert",
    ),
    WittiotSensorEntityDescription(
        key=TYPE_LEAKCH4,
        sensor_type=LEAK_DATA,
        name="CH4 Leak",
        icon="mdi:water-alert",
    ),
    WittiotSensorEntityDescription(
        key=TYPE_LEAKCH1_BATT,
        sensor_type=LEAK_BATT,
        name="CH1 Leak Battery",
        icon="mdi:battery",
    ),
    WittiotSensorEntityDescription(
        key=TYPE_LEAKCH2_BATT,
        sensor_type=LEAK_BATT,
        name="CH2 Leak Battery",
        icon="mdi:battery",
    ),
    WittiotSensorEntityDescription(
        key=TYPE_LEAKCH3_BATT,
        sensor_type=LEAK_BATT,
        name="CH3 Leak Battery",
        icon="mdi:battery",
    ),
    WittiotSensorEntityDescription(
        key=TYPE_LEAKCH4_BATT,
        sensor_type=LEAK_BATT,
        name="CH4 Leak Battery",
        icon="mdi:battery",
    ),
    WittiotSensorEntityDescription(
        key=TYPE_SOILCH1,
        sensor_type=SOIL_DATA,
        name="CH1 Soil",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
    ),
    WittiotSensorEntityDescription(
        key=TYPE_SOILCH2,
        sensor_type=SOIL_DATA,
        name="CH2 Soil",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
    ),
    WittiotSensorEntityDescription(
        key=TYPE_SOILCH3,
        sensor_type=SOIL_DATA,
        name="CH3 Soil",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
    ),
    WittiotSensorEntityDescription(
        key=TYPE_SOILCH4,
        sensor_type=SOIL_DATA,
        name="CH4 Soil",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
    ),
    WittiotSensorEntityDescription(
        key=TYPE_SOILCH5,
        sensor_type=SOIL_DATA,
        name="CH5 Soil",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
    ),
    WittiotSensorEntityDescription(
        key=TYPE_SOILCH6,
        sensor_type=SOIL_DATA,
        name="CH6 Soil",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
    ),
    WittiotSensorEntityDescription(
        key=TYPE_SOILCH7,
        sensor_type=SOIL_DATA,
        name="CH7 Soil",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
    ),
    WittiotSensorEntityDescription(
        key=TYPE_SOILCH8,
        sensor_type=SOIL_DATA,
        name="CH8 Soil",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
    ),
    WittiotSensorEntityDescription(
        key=TYPE_SOILCH1_BATT,
        sensor_type=SOIL_BATT,
        name="CH1 Soil Battery",
        icon="mdi:battery",
    ),
    WittiotSensorEntityDescription(
        key=TYPE_SOILCH2_BATT,
        sensor_type=SOIL_BATT,
        name="CH2 Soil Battery",
        icon="mdi:battery",
    ),
    WittiotSensorEntityDescription(
        key=TYPE_SOILCH3_BATT,
        sensor_type=SOIL_BATT,
        name="CH3 Soil Battery",
        icon="mdi:battery",
    ),
    WittiotSensorEntityDescription(
        key=TYPE_SOILCH4_BATT,
        sensor_type=SOIL_BATT,
        name="CH4 Soil Battery",
        icon="mdi:battery",
    ),
    WittiotSensorEntityDescription(
        key=TYPE_SOILCH5_BATT,
        sensor_type=SOIL_BATT,
        name="CH5 Soil Battery",
        icon="mdi:battery",
    ),
    WittiotSensorEntityDescription(
        key=TYPE_SOILCH6_BATT,
        sensor_type=SOIL_BATT,
        name="CH6 Soil Battery",
        icon="mdi:battery",
    ),
    WittiotSensorEntityDescription(
        key=TYPE_SOILCH7_BATT,
        sensor_type=SOIL_BATT,
        name="CH7 Soil Battery",
        icon="mdi:battery",
    ),
    WittiotSensorEntityDescription(
        key=TYPE_SOILCH8_BATT,
        sensor_type=SOIL_BATT,
        name="CH8 Soil Battery",
        icon="mdi:battery",
    ),
    WittiotSensorEntityDescription(
        key=TYPE_TEMPCH1,
        sensor_type=TEMPHUMI_DATA,
        name="CH1 T&H Temp",
        native_unit_of_measurement="°F",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WittiotSensorEntityDescription(
        key=TYPE_TEMPCH2,
        sensor_type=TEMPHUMI_DATA,
        name="CH2 T&H Temp",
        native_unit_of_measurement="°F",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WittiotSensorEntityDescription(
        key=TYPE_TEMPCH3,
        sensor_type=TEMPHUMI_DATA,
        name="CH3 T&H Temp",
        native_unit_of_measurement="°F",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WittiotSensorEntityDescription(
        key=TYPE_TEMPCH4,
        sensor_type=TEMPHUMI_DATA,
        name="CH4 T&H Temp",
        native_unit_of_measurement="°F",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WittiotSensorEntityDescription(
        key=TYPE_TEMPCH5,
        sensor_type=TEMPHUMI_DATA,
        name="CH5 T&H Temp",
        native_unit_of_measurement="°F",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WittiotSensorEntityDescription(
        key=TYPE_TEMPCH6,
        sensor_type=TEMPHUMI_DATA,
        name="CH6 T&H Temp",
        native_unit_of_measurement="°F",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WittiotSensorEntityDescription(
        key=TYPE_TEMPCH7,
        sensor_type=TEMPHUMI_DATA,
        name="CH7 T&H Temp",
        native_unit_of_measurement="°F",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WittiotSensorEntityDescription(
        key=TYPE_TEMPCH8,
        sensor_type=TEMPHUMI_DATA,
        name="CH8 T&H Temp",
        native_unit_of_measurement="°F",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WittiotSensorEntityDescription(
        key=TYPE_HUMICH1,
        sensor_type=TEMPHUMI_DATA,
        name="CH1 T&H Humidity",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
    ),
    WittiotSensorEntityDescription(
        key=TYPE_HUMICH2,
        sensor_type=TEMPHUMI_DATA,
        name="CH2 T&H Humidity",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
    ),
    WittiotSensorEntityDescription(
        key=TYPE_HUMICH3,
        sensor_type=TEMPHUMI_DATA,
        name="CH3 T&H Humidity",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
    ),
    WittiotSensorEntityDescription(
        key=TYPE_HUMICH4,
        sensor_type=TEMPHUMI_DATA,
        name="CH4 T&H Humidity",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
    ),
    WittiotSensorEntityDescription(
        key=TYPE_HUMICH5,
        sensor_type=TEMPHUMI_DATA,
        name="CH5 T&H Humidity",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
    ),
    WittiotSensorEntityDescription(
        key=TYPE_HUMICH6,
        sensor_type=TEMPHUMI_DATA,
        name="CH6 T&H Humidity",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
    ),
    WittiotSensorEntityDescription(
        key=TYPE_HUMICH7,
        sensor_type=TEMPHUMI_DATA,
        name="CH7 T&H Humidity",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
    ),
    WittiotSensorEntityDescription(
        key=TYPE_HUMICH8,
        sensor_type=TEMPHUMI_DATA,
        name="CH8 T&H Humidity",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
    ),
    WittiotSensorEntityDescription(
        key=TYPE_TEMPCH1_BATT,
        sensor_type=TEMPHUMI_BATT,
        name="CH1 T&H Battery",
        icon="mdi:battery",
    ),
    WittiotSensorEntityDescription(
        key=TYPE_TEMPCH2_BATT,
        sensor_type=TEMPHUMI_BATT,
        name="CH2 T&H Battery",
        icon="mdi:battery",
    ),
    WittiotSensorEntityDescription(
        key=TYPE_TEMPCH3_BATT,
        sensor_type=TEMPHUMI_BATT,
        name="CH3 T&H Battery",
        icon="mdi:battery",
    ),
    WittiotSensorEntityDescription(
        key=TYPE_TEMPCH4_BATT,
        sensor_type=TEMPHUMI_BATT,
        name="CH4 T&H Battery",
        icon="mdi:battery",
    ),
    WittiotSensorEntityDescription(
        key=TYPE_TEMPCH5_BATT,
        sensor_type=TEMPHUMI_BATT,
        name="CH5 T&H Battery",
        icon="mdi:battery",
    ),
    WittiotSensorEntityDescription(
        key=TYPE_TEMPCH6_BATT,
        sensor_type=TEMPHUMI_BATT,
        name="CH6 T&H Battery",
        icon="mdi:battery",
    ),
    WittiotSensorEntityDescription(
        key=TYPE_TEMPCH7_BATT,
        sensor_type=TEMPHUMI_BATT,
        name="CH7 T&H Battery",
        icon="mdi:battery",
    ),
    WittiotSensorEntityDescription(
        key=TYPE_TEMPCH8_BATT,
        sensor_type=TEMPHUMI_BATT,
        name="CH8 T&H Battery",
        icon="mdi:battery",
    ),
    WittiotSensorEntityDescription(
        key=TYPE_ONLYTEMPCH1,
        sensor_type=TEMP_DATA,
        name="CH1 Temp",
        native_unit_of_measurement="°F",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WittiotSensorEntityDescription(
        key=TYPE_ONLYTEMPCH2,
        sensor_type=TEMP_DATA,
        name="CH2 Temp",
        native_unit_of_measurement="°F",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WittiotSensorEntityDescription(
        key=TYPE_ONLYTEMPCH3,
        sensor_type=TEMP_DATA,
        name="CH3 Temp",
        native_unit_of_measurement="°F",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WittiotSensorEntityDescription(
        key=TYPE_ONLYTEMPCH4,
        sensor_type=TEMP_DATA,
        name="CH4 Temp",
        native_unit_of_measurement="°F",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WittiotSensorEntityDescription(
        key=TYPE_ONLYTEMPCH5,
        sensor_type=TEMP_DATA,
        name="CH5 Temp",
        native_unit_of_measurement="°F",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WittiotSensorEntityDescription(
        key=TYPE_ONLYTEMPCH6,
        sensor_type=TEMP_DATA,
        name="CH6 Temp",
        native_unit_of_measurement="°F",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WittiotSensorEntityDescription(
        key=TYPE_ONLYTEMPCH7,
        sensor_type=TEMP_DATA,
        name="CH7 Temp",
        native_unit_of_measurement="°F",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WittiotSensorEntityDescription(
        key=TYPE_ONLYTEMPCH8,
        sensor_type=TEMP_DATA,
        name="CH8 Temp",
        native_unit_of_measurement="°F",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WittiotSensorEntityDescription(
        key=TYPE_ONLYTEMPCH1_BATT,
        sensor_type=TEMP_BATT,
        name="CH1 Temp Battery",
        icon="mdi:battery",
    ),
    WittiotSensorEntityDescription(
        key=TYPE_ONLYTEMPCH2_BATT,
        sensor_type=TEMP_BATT,
        name="CH2 Temp Battery",
        icon="mdi:battery",
    ),
    WittiotSensorEntityDescription(
        key=TYPE_ONLYTEMPCH3_BATT,
        sensor_type=TEMP_BATT,
        name="CH3 Temp Battery",
        icon="mdi:battery",
    ),
    WittiotSensorEntityDescription(
        key=TYPE_ONLYTEMPCH4_BATT,
        sensor_type=TEMP_BATT,
        name="CH4 Temp Battery",
        icon="mdi:battery",
    ),
    WittiotSensorEntityDescription(
        key=TYPE_ONLYTEMPCH5_BATT,
        sensor_type=TEMP_BATT,
        name="CH5 Temp Battery",
        icon="mdi:battery",
    ),
    WittiotSensorEntityDescription(
        key=TYPE_ONLYTEMPCH6_BATT,
        sensor_type=TEMP_BATT,
        name="CH6 Temp Battery",
        icon="mdi:battery",
    ),
    WittiotSensorEntityDescription(
        key=TYPE_ONLYTEMPCH7_BATT,
        sensor_type=TEMP_BATT,
        name="CH7 Temp Battery",
        icon="mdi:battery",
    ),
    WittiotSensorEntityDescription(
        key=TYPE_ONLYTEMPCH8_BATT,
        sensor_type=TEMP_BATT,
        name="CH8 Temp Battery",
        icon="mdi:battery",
    ),
    WittiotSensorEntityDescription(
        key=TYPE_LEAFCH1,
        sensor_type=LEAF_DATA,
        name="CH1 Leaf",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
    ),
    WittiotSensorEntityDescription(
        key=TYPE_LEAFCH2,
        sensor_type=LEAF_DATA,
        name="CH2 Leaf",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
    ),
    WittiotSensorEntityDescription(
        key=TYPE_LEAFCH3,
        sensor_type=LEAF_DATA,
        name="CH3 Leaf",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
    ),
    WittiotSensorEntityDescription(
        key=TYPE_LEAFCH4,
        sensor_type=LEAF_DATA,
        name="CH4 Leaf",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
    ),
    WittiotSensorEntityDescription(
        key=TYPE_LEAFCH5,
        sensor_type=LEAF_DATA,
        name="CH5 Leaf",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
    ),
    WittiotSensorEntityDescription(
        key=TYPE_LEAFCH6,
        sensor_type=LEAF_DATA,
        name="CH6 Leaf",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
    ),
    WittiotSensorEntityDescription(
        key=TYPE_LEAFCH7,
        sensor_type=LEAF_DATA,
        name="CH7 Leaf",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
    ),
    WittiotSensorEntityDescription(
        key=TYPE_LEAFCH8,
        sensor_type=LEAF_DATA,
        name="CH8 Leaf",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
    ),
    WittiotSensorEntityDescription(
        key=TYPE_LEAFCH1_BATT,
        sensor_type=LEAF_BATT,
        name="CH1 Leaf Battery",
        icon="mdi:battery",
    ),
    WittiotSensorEntityDescription(
        key=TYPE_LEAFCH2_BATT,
        sensor_type=LEAF_BATT,
        name="CH2 Leaf Battery",
        icon="mdi:battery",
    ),
    WittiotSensorEntityDescription(
        key=TYPE_LEAFCH3_BATT,
        sensor_type=LEAF_BATT,
        name="CH3 Leaf Battery",
        icon="mdi:battery",
    ),
    WittiotSensorEntityDescription(
        key=TYPE_LEAFCH4_BATT,
        sensor_type=LEAF_BATT,
        name="CH4 Leaf Battery",
        icon="mdi:battery",
    ),
    WittiotSensorEntityDescription(
        key=TYPE_LEAFCH5_BATT,
        sensor_type=LEAF_BATT,
        name="CH5 Leaf Battery",
        icon="mdi:battery",
    ),
    WittiotSensorEntityDescription(
        key=TYPE_LEAFCH6_BATT,
        sensor_type=LEAF_BATT,
        name="CH6 Leaf Battery",
        icon="mdi:battery",
    ),
    WittiotSensorEntityDescription(
        key=TYPE_LEAFCH7_BATT,
        sensor_type=LEAF_BATT,
        name="CH7 Leaf Battery",
        icon="mdi:battery",
    ),
    WittiotSensorEntityDescription(
        key=TYPE_LEAFCH8_BATT,
        sensor_type=LEAF_BATT,
        name="CH8 Leaf Battery",
        icon="mdi:battery",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Wittiot sensor entities based on a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    sensors = []
    for desc in SENSOR_DESCRIPTIONS:
        if coordinator.data.get(desc.key) not in ("", "--", "--.-", "None"):
            sensors.append(
                LocalWittiotSensor(
                    coordinator,
                    entry.data[CONF_IP],
                    entry.data[DEVICE_NAME],
                    desc,
                )
            )
    async_add_entities(sensors, True)


class LocalWittiotSensor(CoordinatorEntity[WittiotDataUpdateCoordinator], SensorEntity):
    """Define an Local sensor."""

    _attr_has_entity_name = True
    entity_description: WittiotSensorEntityDescription

    def __init__(
        self,
        coordinator: WittiotDataUpdateCoordinator,
        ipadrr: str,
        devname: str,
        description: WittiotSensorEntityDescription,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{devname}_{description.sensor_type}")},
            manufacturer="WittIOT",
            name=f"{devname}_{description.sensor_type}",
            model=self.coordinator.data["ver"],
            configuration_url=f"http://{ipadrr}",
        )
        self._attr_unique_id = f"{devname}_{description.key}"
        self.entity_description = description

    @property
    def native_value(self) -> StateType:
        """Return the state."""
        state = self.coordinator.data[self.entity_description.key]
        return state
