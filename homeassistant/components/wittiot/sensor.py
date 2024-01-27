"""Platform for sensor integration."""

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
    UnitOfVolumetricFlux,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import WittiotDataUpdateCoordinator

SENSOR_DESCRIPTIONS = (
    SensorEntityDescription(
        key="tempinf",
        translation_key="tempinf",
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="tempf",
        translation_key="tempf",
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="feellike",
        translation_key="feellike",
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="dewpoint",
        translation_key="dewpoint",
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="tf_co2",
        translation_key="tf_co2",
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="humidityin",
        translation_key="humidityin",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
    ),
    SensorEntityDescription(
        key="humidity",
        translation_key="humidity",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
    ),
    SensorEntityDescription(
        key="humi_co2",
        translation_key="humi_co2",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
    ),
    SensorEntityDescription(
        key="baromrelin",
        translation_key="baromrelin",
        native_unit_of_measurement=UnitOfPressure.INHG,
        device_class=SensorDeviceClass.PRESSURE,
    ),
    SensorEntityDescription(
        key="baromabsin",
        translation_key="baromabsin",
        native_unit_of_measurement=UnitOfPressure.INHG,
        device_class=SensorDeviceClass.PRESSURE,
    ),
    SensorEntityDescription(
        key="winddir",
        translation_key="winddir",
        icon="mdi:weather-windy",
        native_unit_of_measurement=DEGREE,
    ),
    SensorEntityDescription(
        key="windspeedmph",
        translation_key="windspeedmph",
        device_class=SensorDeviceClass.WIND_SPEED,
        native_unit_of_measurement=UnitOfSpeed.MILES_PER_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="windgustmph",
        translation_key="windgustmph",
        device_class=SensorDeviceClass.WIND_SPEED,
        native_unit_of_measurement=UnitOfSpeed.MILES_PER_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="daywindmax",
        translation_key="daywindmax",
        device_class=SensorDeviceClass.WIND_SPEED,
        native_unit_of_measurement=UnitOfSpeed.MILES_PER_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="uv",
        translation_key="uv",
        native_unit_of_measurement="index",
        device_class=SensorDeviceClass.ILLUMINANCE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="solarradiation",
        translation_key="solarradiation",
        native_unit_of_measurement=UnitOfIrradiance.WATTS_PER_SQUARE_METER,
        device_class=SensorDeviceClass.IRRADIANCE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="rainratein",
        translation_key="rainratein",
        native_unit_of_measurement=UnitOfVolumetricFlux.INCHES_PER_HOUR,
        device_class=SensorDeviceClass.PRECIPITATION_INTENSITY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="eventrainin",
        translation_key="eventrainin",
        native_unit_of_measurement=UnitOfPrecipitationDepth.INCHES,
        device_class=SensorDeviceClass.PRECIPITATION,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="dailyrainin",
        translation_key="dailyrainin",
        device_class=SensorDeviceClass.PRECIPITATION,
        native_unit_of_measurement=UnitOfPrecipitationDepth.INCHES,
        state_class=SensorStateClass.TOTAL,
    ),
    SensorEntityDescription(
        key="weeklyrainin",
        translation_key="weeklyrainin",
        device_class=SensorDeviceClass.PRECIPITATION,
        native_unit_of_measurement=UnitOfPrecipitationDepth.INCHES,
        state_class=SensorStateClass.TOTAL,
    ),
    SensorEntityDescription(
        key="monthlyrainin",
        translation_key="monthlyrainin",
        device_class=SensorDeviceClass.PRECIPITATION,
        native_unit_of_measurement=UnitOfPrecipitationDepth.INCHES,
        state_class=SensorStateClass.TOTAL,
    ),
    SensorEntityDescription(
        key="yearlyrainin",
        translation_key="yearlyrainin",
        device_class=SensorDeviceClass.PRECIPITATION,
        native_unit_of_measurement=UnitOfPrecipitationDepth.INCHES,
        state_class=SensorStateClass.TOTAL,
    ),
    SensorEntityDescription(
        key="rrain_piezo",
        translation_key="rrain_piezo",
        native_unit_of_measurement=UnitOfVolumetricFlux.INCHES_PER_HOUR,
        device_class=SensorDeviceClass.PRECIPITATION_INTENSITY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="erain_piezo",
        translation_key="erain_piezo",
        device_class=SensorDeviceClass.PRECIPITATION,
        native_unit_of_measurement=UnitOfPrecipitationDepth.INCHES,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="drain_piezo",
        translation_key="drain_piezo",
        device_class=SensorDeviceClass.PRECIPITATION,
        native_unit_of_measurement=UnitOfPrecipitationDepth.INCHES,
        state_class=SensorStateClass.TOTAL,
    ),
    SensorEntityDescription(
        key="wrain_piezo",
        translation_key="wrain_piezo",
        device_class=SensorDeviceClass.PRECIPITATION,
        native_unit_of_measurement=UnitOfPrecipitationDepth.INCHES,
        state_class=SensorStateClass.TOTAL,
    ),
    SensorEntityDescription(
        key="mrain_piezo",
        translation_key="mrain_piezo",
        device_class=SensorDeviceClass.PRECIPITATION,
        native_unit_of_measurement=UnitOfPrecipitationDepth.INCHES,
        state_class=SensorStateClass.TOTAL,
    ),
    SensorEntityDescription(
        key="yrain_piezo",
        translation_key="yrain_piezo",
        device_class=SensorDeviceClass.PRECIPITATION,
        native_unit_of_measurement=UnitOfPrecipitationDepth.INCHES,
        state_class=SensorStateClass.TOTAL,
    ),
    SensorEntityDescription(
        key="co2in",
        translation_key="co2in",
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        device_class=SensorDeviceClass.CO2,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="co2",
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        device_class=SensorDeviceClass.CO2,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="co2in_24h",
        translation_key="co2in_24h",
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        device_class=SensorDeviceClass.CO2,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="co2_24h",
        translation_key="co2_24h",
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        device_class=SensorDeviceClass.CO2,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="pm25_co2",
        translation_key="pm25_co2",
        device_class=SensorDeviceClass.PM25,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="pm25_aqi_co2",
        translation_key="pm25_aqi_co2",
        device_class=SensorDeviceClass.AQI,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="pm25_24h_co2",
        translation_key="pm25_24h_co2",
        device_class=SensorDeviceClass.AQI,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="pm10_co2",
        translation_key="pm10_co2",
        device_class=SensorDeviceClass.PM10,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="pm10_aqi_co2",
        translation_key="pm10_aqi_co2",
        device_class=SensorDeviceClass.AQI,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="pm10_24h_co2",
        translation_key="pm10_24h_co2",
        device_class=SensorDeviceClass.AQI,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="lightning",
        translation_key="lightning",
        icon="mdi:lightning-bolt",
        native_unit_of_measurement=UnitOfLength.MILES,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="lightning_time",
        translation_key="lightning_time",
        icon="mdi:lightning-bolt",
    ),
    SensorEntityDescription(
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
    device_name = entry.unique_id
    async_add_entities(
        MainDevWittiotSensor(coordinator, device_name, desc)
        for desc in SENSOR_DESCRIPTIONS
        if desc.key in coordinator.data
    )


class MainDevWittiotSensor(
    CoordinatorEntity[WittiotDataUpdateCoordinator], SensorEntity
):
    """Define a Local sensor."""

    _attr_has_entity_name = True
    entity_description: SensorEntityDescription

    def __init__(
        self,
        coordinator: WittiotDataUpdateCoordinator,
        device_name: str | None,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{device_name}")},
            manufacturer="WittIOT",
            name=f"{device_name}",
            model=coordinator.data["ver"],
            configuration_url=f"http://{coordinator.config_entry.data[CONF_HOST]}",
        )
        self._attr_unique_id = f"{device_name}_{description.key}"
        self.entity_description = description

    @property
    def native_value(self) -> str | int | float | None:
        """Return the state."""
        return self.coordinator.data.get(self.entity_description.key)
