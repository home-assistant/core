"""Support for Ambient Weather Network sensors."""

from __future__ import annotations

from datetime import datetime

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONCENTRATION_PARTS_PER_MILLION,
    CONF_MAC,
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

from . import AmbientNetworkConfigEntry
from .coordinator import AmbientNetworkDataUpdateCoordinator
from .entity import AmbientNetworkEntity

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


SENSOR_DESCRIPTIONS = (
    SensorEntityDescription(
        key=TYPE_AQI_PM25,
        translation_key="pm25_aqi",
        device_class=SensorDeviceClass.AQI,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
    ),
    SensorEntityDescription(
        key=TYPE_AQI_PM25_24H,
        translation_key="pm25_aqi_24h_average",
        device_class=SensorDeviceClass.AQI,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key=TYPE_BAROMABSIN,
        translation_key="absolute_pressure",
        native_unit_of_measurement=UnitOfPressure.INHG,
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key=TYPE_BAROMRELIN,
        translation_key="relative_pressure",
        native_unit_of_measurement=UnitOfPressure.INHG,
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
    ),
    SensorEntityDescription(
        key=TYPE_CO2,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        device_class=SensorDeviceClass.CO2,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key=TYPE_DAILYRAININ,
        translation_key="daily_rain",
        native_unit_of_measurement=UnitOfPrecipitationDepth.INCHES,
        device_class=SensorDeviceClass.PRECIPITATION,
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=2,
    ),
    SensorEntityDescription(
        key=TYPE_DEWPOINT,
        translation_key="dew_point",
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    SensorEntityDescription(
        key=TYPE_FEELSLIKE,
        translation_key="feels_like",
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    SensorEntityDescription(
        key=TYPE_HOURLYRAININ,
        translation_key="hourly_rain",
        native_unit_of_measurement=UnitOfVolumetricFlux.INCHES_PER_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.PRECIPITATION_INTENSITY,
        suggested_display_precision=2,
    ),
    SensorEntityDescription(
        key=TYPE_HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    SensorEntityDescription(
        key=TYPE_LASTRAIN,
        translation_key="last_rain",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key=TYPE_LIGHTNING_PER_DAY,
        translation_key="lightning_strikes_per_day",
        native_unit_of_measurement="strikes",
        state_class=SensorStateClass.TOTAL,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key=TYPE_LIGHTNING_PER_HOUR,
        translation_key="lightning_strikes_per_hour",
        native_unit_of_measurement="strikes/hour",
        state_class=SensorStateClass.TOTAL,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key=TYPE_LIGHTNING_DISTANCE,
        translation_key="lightning_distance",
        native_unit_of_measurement=UnitOfLength.MILES,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key=TYPE_MAXDAILYGUST,
        translation_key="max_daily_gust",
        native_unit_of_measurement=UnitOfSpeed.MILES_PER_HOUR,
        device_class=SensorDeviceClass.WIND_SPEED,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    SensorEntityDescription(
        key=TYPE_MONTHLYRAININ,
        translation_key="monthly_rain",
        native_unit_of_measurement=UnitOfPrecipitationDepth.INCHES,
        device_class=SensorDeviceClass.PRECIPITATION,
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key=TYPE_PM25_24H,
        translation_key="pm25_24h_average",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        device_class=SensorDeviceClass.PM25,
        suggested_display_precision=1,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key=TYPE_PM25,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        device_class=SensorDeviceClass.PM25,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key=TYPE_SOLARRADIATION,
        native_unit_of_measurement=UnitOfIrradiance.WATTS_PER_SQUARE_METER,
        device_class=SensorDeviceClass.IRRADIANCE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key=TYPE_TEMPF,
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    SensorEntityDescription(
        key=TYPE_UV,
        translation_key="uv_index",
        native_unit_of_measurement="index",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    SensorEntityDescription(
        key=TYPE_WEEKLYRAININ,
        translation_key="weekly_rain",
        native_unit_of_measurement=UnitOfPrecipitationDepth.INCHES,
        device_class=SensorDeviceClass.PRECIPITATION,
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key=TYPE_WINDDIR,
        translation_key="wind_direction",
        native_unit_of_measurement=DEGREE,
        suggested_display_precision=0,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key=TYPE_WINDGUSTMPH,
        translation_key="wind_gust",
        native_unit_of_measurement=UnitOfSpeed.MILES_PER_HOUR,
        device_class=SensorDeviceClass.WIND_SPEED,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    SensorEntityDescription(
        key=TYPE_WINDSPEEDMPH,
        native_unit_of_measurement=UnitOfSpeed.MILES_PER_HOUR,
        device_class=SensorDeviceClass.WIND_SPEED,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    SensorEntityDescription(
        key=TYPE_YEARLYRAININ,
        translation_key="yearly_rain",
        native_unit_of_measurement=UnitOfPrecipitationDepth.INCHES,
        device_class=SensorDeviceClass.PRECIPITATION,
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AmbientNetworkConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Ambient Network sensor entities."""

    coordinator = entry.runtime_data
    if coordinator.config_entry is not None:
        async_add_entities(
            AmbientNetworkSensor(
                coordinator,
                description,
                coordinator.config_entry.data[CONF_MAC],
            )
            for description in SENSOR_DESCRIPTIONS
            if coordinator.data.get(description.key) is not None
        )


class AmbientNetworkSensor(AmbientNetworkEntity, SensorEntity):
    """A sensor implementation for an Ambient Weather Network sensor."""

    def __init__(
        self,
        coordinator: AmbientNetworkDataUpdateCoordinator,
        description: SensorEntityDescription,
        mac_address: str,
    ) -> None:
        """Initialize a sensor object."""
        super().__init__(coordinator, description, mac_address)

    def _update_attrs(self) -> None:
        """Update sensor attributes."""
        value = self.coordinator.data.get(self.entity_description.key)

        # Treatments for special units.
        if value is not None and self.device_class == SensorDeviceClass.TIMESTAMP:
            value = datetime.fromtimestamp(
                value / 1000, tz=dt_util.get_default_time_zone()
            )

        self._attr_available = value is not None
        self._attr_native_value = value

        if self.coordinator.last_measured is not None:
            self._attr_extra_state_attributes = {
                "last_measured": self.coordinator.last_measured
            }
