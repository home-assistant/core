"""Platform for sensor integration."""
import dataclasses

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
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import WittiotDataUpdateCoordinator


@dataclasses.dataclass(frozen=True)
class WittiotSensorEntityDescription(SensorEntityDescription):
    """Class describing WittIOT sensor entities."""


SENSOR_DESCRIPTIONS = (
    WittiotSensorEntityDescription(
        key="tempinf",
        translation_key="tempinf",
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WittiotSensorEntityDescription(
        key="tempf",
        translation_key="tempf",
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WittiotSensorEntityDescription(
        key="feellike",
        translation_key="feellike",
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WittiotSensorEntityDescription(
        key="dewpoint",
        translation_key="dewpoint",
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WittiotSensorEntityDescription(
        key="tf_co2",
        translation_key="tf_co2",
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WittiotSensorEntityDescription(
        key="humidityin",
        translation_key="humidityin",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
    ),
    WittiotSensorEntityDescription(
        key="humidity",
        translation_key="humidity",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
    ),
    WittiotSensorEntityDescription(
        key="humi_co2",
        translation_key="humi_co2",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
    ),
    WittiotSensorEntityDescription(
        key="baromrelin",
        translation_key="baromrelin",
        native_unit_of_measurement=UnitOfPressure.INHG,
        device_class=SensorDeviceClass.PRESSURE,
    ),
    WittiotSensorEntityDescription(
        key="baromabsin",
        translation_key="baromabsin",
        native_unit_of_measurement=UnitOfPressure.INHG,
        device_class=SensorDeviceClass.PRESSURE,
    ),
    WittiotSensorEntityDescription(
        key="winddir",
        translation_key="winddir",
        icon="mdi:weather-windy",
        native_unit_of_measurement=DEGREE,
    ),
    WittiotSensorEntityDescription(
        key="windspeedmph",
        translation_key="windspeedmph",
        icon="mdi:weather-windy",
        native_unit_of_measurement=UnitOfSpeed.MILES_PER_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WittiotSensorEntityDescription(
        key="windgustmph",
        translation_key="windgustmph",
        icon="mdi:weather-windy",
        native_unit_of_measurement=UnitOfSpeed.MILES_PER_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WittiotSensorEntityDescription(
        key="daywindmax",
        translation_key="daywindmax",
        icon="mdi:weather-windy",
        native_unit_of_measurement=UnitOfSpeed.MILES_PER_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WittiotSensorEntityDescription(
        key="uv",
        translation_key="uv",
        native_unit_of_measurement="Index",
        device_class=SensorDeviceClass.ILLUMINANCE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WittiotSensorEntityDescription(
        key="solarradiation",
        translation_key="solarradiation",
        native_unit_of_measurement=UnitOfIrradiance.WATTS_PER_SQUARE_METER,
        device_class=SensorDeviceClass.ILLUMINANCE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WittiotSensorEntityDescription(
        key="rainratein",
        translation_key="rainratein",
        icon="mdi:water",
        native_unit_of_measurement=UnitOfPrecipitationDepth.INCHES,
        device_class=SensorDeviceClass.PRECIPITATION_INTENSITY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WittiotSensorEntityDescription(
        key="eventrainin",
        translation_key="eventrainin",
        icon="mdi:water",
        native_unit_of_measurement=UnitOfPrecipitationDepth.INCHES,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WittiotSensorEntityDescription(
        key="dailyrainin",
        translation_key="dailyrainin",
        icon="mdi:water",
        native_unit_of_measurement=UnitOfPrecipitationDepth.INCHES,
        state_class=SensorStateClass.TOTAL,
    ),
    WittiotSensorEntityDescription(
        key="weeklyrainin",
        translation_key="weeklyrainin",
        icon="mdi:water",
        native_unit_of_measurement=UnitOfPrecipitationDepth.INCHES,
        state_class=SensorStateClass.TOTAL,
    ),
    WittiotSensorEntityDescription(
        key="monthlyrainin",
        translation_key="monthlyrainin",
        icon="mdi:water",
        native_unit_of_measurement=UnitOfPrecipitationDepth.INCHES,
        state_class=SensorStateClass.TOTAL,
    ),
    WittiotSensorEntityDescription(
        key="yearlyrainin",
        translation_key="yearlyrainin",
        icon="mdi:water",
        native_unit_of_measurement=UnitOfPrecipitationDepth.INCHES,
        state_class=SensorStateClass.TOTAL,
    ),
    WittiotSensorEntityDescription(
        key="rrain_piezo",
        translation_key="rrain_piezo",
        icon="mdi:water",
        native_unit_of_measurement=UnitOfPrecipitationDepth.INCHES,
        device_class=SensorDeviceClass.PRECIPITATION_INTENSITY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WittiotSensorEntityDescription(
        key="erain_piezo",
        translation_key="erain_piezo",
        icon="mdi:water",
        native_unit_of_measurement=UnitOfPrecipitationDepth.INCHES,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WittiotSensorEntityDescription(
        key="drain_piezo",
        translation_key="drain_piezo",
        icon="mdi:water",
        native_unit_of_measurement=UnitOfPrecipitationDepth.INCHES,
        state_class=SensorStateClass.TOTAL,
    ),
    WittiotSensorEntityDescription(
        key="wrain_piezo",
        translation_key="wrain_piezo",
        icon="mdi:water",
        native_unit_of_measurement=UnitOfPrecipitationDepth.INCHES,
        state_class=SensorStateClass.TOTAL,
    ),
    WittiotSensorEntityDescription(
        key="mrain_piezo",
        translation_key="mrain_piezo",
        icon="mdi:water",
        native_unit_of_measurement=UnitOfPrecipitationDepth.INCHES,
        state_class=SensorStateClass.TOTAL,
    ),
    WittiotSensorEntityDescription(
        key="yrain_piezo",
        translation_key="yrain_piezo",
        icon="mdi:water",
        native_unit_of_measurement=UnitOfPrecipitationDepth.INCHES,
        state_class=SensorStateClass.TOTAL,
    ),
    WittiotSensorEntityDescription(
        key="co2in",
        translation_key="co2in",
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        device_class=SensorDeviceClass.CO2,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WittiotSensorEntityDescription(
        key="co2",
        translation_key="co2",
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        device_class=SensorDeviceClass.CO2,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WittiotSensorEntityDescription(
        key="co2in_24h",
        translation_key="co2in_24h",
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        device_class=SensorDeviceClass.CO2,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WittiotSensorEntityDescription(
        key="co2_24h",
        translation_key="co2_24h",
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        device_class=SensorDeviceClass.CO2,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WittiotSensorEntityDescription(
        key="pm25_co2",
        translation_key="pm25_co2",
        device_class=SensorDeviceClass.PM25,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WittiotSensorEntityDescription(
        key="pm25_aqi_co2",
        translation_key="pm25_aqi_co2",
        device_class=SensorDeviceClass.AQI,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WittiotSensorEntityDescription(
        key="pm25_24h_co2",
        translation_key="pm25_24h_co2",
        device_class=SensorDeviceClass.AQI,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WittiotSensorEntityDescription(
        key="pm10_co2",
        translation_key="pm10_co2",
        device_class=SensorDeviceClass.PM10,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WittiotSensorEntityDescription(
        key="pm10_aqi_co2",
        translation_key="pm10_aqi_co2",
        device_class=SensorDeviceClass.AQI,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WittiotSensorEntityDescription(
        key="pm10_24h_co2",
        translation_key="pm10_24h_co2",
        device_class=SensorDeviceClass.AQI,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WittiotSensorEntityDescription(
        key="lightning",
        translation_key="lightning",
        icon="mdi:lightning-bolt",
        native_unit_of_measurement=UnitOfLength.MILES,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WittiotSensorEntityDescription(
        key="lightning_time",
        translation_key="lightning_time",
        icon="mdi:lightning-bolt",
    ),
    WittiotSensorEntityDescription(
        key="lightning_num",
        translation_key="lightning_num",
        icon="mdi:lightning-bolt",
        state_class=SensorStateClass.TOTAL,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Wittiot sensor entities based on a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        MainDevWittiotSensor(coordinator, entry, desc)
        for desc in SENSOR_DESCRIPTIONS
        if desc.key in coordinator.data
    )


class MainDevWittiotSensor(
    CoordinatorEntity[WittiotDataUpdateCoordinator], SensorEntity
):
    """Define a Local sensor."""

    _attr_has_entity_name = True
    entity_description: WittiotSensorEntityDescription

    def __init__(
        self,
        coordinator: WittiotDataUpdateCoordinator,
        entry: ConfigEntry,
        description: WittiotSensorEntityDescription,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.unique_id}")},
            manufacturer="WittIOT",
            name=f"{entry.unique_id}",
            model=coordinator.data["ver"],
            configuration_url=f"http://{entry.data[CONF_HOST]}",
        )
        self._attr_unique_id = f"{entry.unique_id}_{description.key}"
        self.entity_description = description

    @property
    def native_value(self) -> str | int | float | None:
        """Return the state."""
        return self.coordinator.data.get(self.entity_description.key)
