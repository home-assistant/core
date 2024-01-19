"""Platform for sensor integration."""
import dataclasses
from typing import Final

from wittiot import MultiSensorInfo, WittiotDataTypes

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONCENTRATION_PARTS_PER_MILLION,
    CONF_HOST,
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
from homeassistant.helpers.update_coordinator import CoordinatorEntity

# from homeassistant.helpers.entity import EntityDescription
from .const import DEVICE_NAME, DOMAIN, MAIN_DATA
from .coordinator import WittiotDataUpdateCoordinator

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


@dataclasses.dataclass(frozen=True, kw_only=True)
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
)

WITTIOT_SENSORS_MAPPING: Final = {
    WittiotDataTypes.TEMPERATURE: WittiotSensorEntityDescription(
        key="TEMPERATURE",
        native_unit_of_measurement="°F",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WittiotDataTypes.HUMIDITY: WittiotSensorEntityDescription(
        key="HUMIDITY",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
    ),
    WittiotDataTypes.PM25: WittiotSensorEntityDescription(
        key="PM25",
        device_class=SensorDeviceClass.PM25,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WittiotDataTypes.AQI: WittiotSensorEntityDescription(
        key="AQI",
        device_class=SensorDeviceClass.AQI,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WittiotDataTypes.LEAK: WittiotSensorEntityDescription(
        key="LEAK",
        icon="mdi:water-alert",
    ),
    WittiotDataTypes.BATTERY: WittiotSensorEntityDescription(
        key="BATTERY",
        icon="mdi:battery",
    ),
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Wittiot sensor entities based on a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    sensors: list[MainDevWittiotSensor | SubDevWittiotSensor] = []
    # Main Device Data
    for desc in SENSOR_DESCRIPTIONS:
        if coordinator.data.get(desc.key) not in ("", "--", "--.-", "None"):
            sensors.append(
                MainDevWittiotSensor(
                    coordinator,
                    entry.data[CONF_HOST],
                    entry.data[DEVICE_NAME],
                    desc,
                )
            )

    # Subdevice Data
    for key in coordinator.data:
        if coordinator.data.get(key) not in ("", "--", "--.-", "None"):
            if key in MultiSensorInfo.SENSOR_INFO:
                mapping = WITTIOT_SENSORS_MAPPING[
                    MultiSensorInfo.SENSOR_INFO[key]["data_type"]
                ]
                description = dataclasses.replace(
                    mapping,
                    key=key,
                    sensor_type=MultiSensorInfo.SENSOR_INFO[key]["dev_type"],
                    name=MultiSensorInfo.SENSOR_INFO[key]["name"],
                )
                sensors.append(
                    SubDevWittiotSensor(
                        coordinator,
                        entry.data[CONF_HOST],
                        entry.data[DEVICE_NAME],
                        description,
                    )
                )

    async_add_entities(sensors, True)


class MainDevWittiotSensor(
    CoordinatorEntity[WittiotDataUpdateCoordinator], SensorEntity
):
    """Define an Local sensor."""

    _attr_has_entity_name = True
    entity_description: WittiotSensorEntityDescription

    def __init__(
        self,
        coordinator: WittiotDataUpdateCoordinator,
        host: str,
        devname: str,
        description: WittiotSensorEntityDescription,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{devname}_{MAIN_DATA}")},
            manufacturer="WittIOT",
            name=f"{devname}_{MAIN_DATA}",
            model=self.coordinator.data["ver"],
            configuration_url=f"http://{host}",
        )
        self._attr_unique_id = f"{devname}_{description.key}"
        self.entity_description = description

    @property
    def native_value(self) -> str | int | float | None:
        """Return the state."""
        state = self.coordinator.data[self.entity_description.key]
        if state not in ("", "--", "--.-", "None"):
            return state
        return None


class SubDevWittiotSensor(
    CoordinatorEntity[WittiotDataUpdateCoordinator], SensorEntity
):
    """Define an Local sensor."""

    _attr_has_entity_name = True
    entity_description: WittiotSensorEntityDescription

    def __init__(
        self,
        coordinator: WittiotDataUpdateCoordinator,
        host: str,
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
            configuration_url=f"http://{host}",
            via_device=(DOMAIN, f"{devname}_{MAIN_DATA}"),
        )
        self._attr_unique_id = f"{devname}_{description.key}"
        self.entity_description = description

    @property
    def native_value(self) -> str | int | float | None:
        """Return the state."""
        state = self.coordinator.data[self.entity_description.key]
        if state not in ("", "--", "--.-", "None"):
            return state
        return None
