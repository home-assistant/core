"""Sensors for the smartweatherudp integration."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from pyweatherflowudp.calc import Quantity
from pyweatherflowudp.const import EVENT_RAPID_WIND
from pyweatherflowudp.device import (
    EVENT_OBSERVATION,
    EVENT_STATUS_UPDATE,
    WeatherFlowDevice,
)
from pyweatherflowudp.enums import PrecipitationType

from homeassistant.components.sensor import (
    DOMAIN as SENSOR_DOMAIN,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    DEGREE,
    LIGHT_LUX,
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    UV_INDEX,
    EntityCategory,
    UnitOfElectricPotential,
    UnitOfIrradiance,
    UnitOfLength,
    UnitOfPrecipitationDepth,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
    UnitOfVolumetricFlux,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.util.unit_system import METRIC_SYSTEM

from .const import DOMAIN, LOGGER

CONCENTRATION_KILOGRAMS_PER_CUBIC_METER = "kg/m³"
CONCENTRATION_POUNDS_PER_CUBIC_FOOT = "lbs/ft³"


@dataclass
class WeatherFlowSensorEntityDescription(SensorEntityDescription):
    """Describes a WeatherFlow sensor entity description."""

    event_subscriptions: list[str] = field(default_factory=lambda: [EVENT_OBSERVATION])
    value_fn: Callable[[Quantity], Quantity] | None = None
    imperial_suggested_unit: None | str = None
    backing_library_attribute: str | None = None


@dataclass
class AirDensityWeatherFlowSensorEntityDescription(WeatherFlowSensorEntityDescription):
    """Custom class to handle the conversion between backing lib and Home Assistant Compatible VOC sensor."""

    imperial_unit_of_measurement: str | None = None


@dataclass
class WeatherFlowWindSensorEntityDescription(WeatherFlowSensorEntityDescription):
    """Describes a WeatherFlow wind sensor entity description."""

    def __post_init__(self) -> None:
        """Post initialisation processing."""
        self.icon = "mdi:weather-windy"
        self.native_unit_of_measurement = UnitOfSpeed.KILOMETERS_PER_HOUR
        self.state_class = SensorStateClass.MEASUREMENT
        self.suggested_display_precision = 2


CUSTOM_SENSORS: tuple[AirDensityWeatherFlowSensorEntityDescription, ...] = (
    AirDensityWeatherFlowSensorEntityDescription(
        key="air_density",
        translation_key="air_density",
        native_unit_of_measurement="µg/m³",
        device_class=SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=5,
    ),
)

SENSORS: tuple[WeatherFlowSensorEntityDescription, ...] = (
    WeatherFlowSensorEntityDescription(
        key="air_temperature",
        translation_key="temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    WeatherFlowSensorEntityDescription(
        key="dew_point_temperature",
        translation_key="dew_point",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    WeatherFlowSensorEntityDescription(
        key="feels_like_temperature",
        translation_key="feels_like",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    WeatherFlowSensorEntityDescription(
        key="wet_bulb_temperature",
        translation_key="wet_bulb_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    WeatherFlowSensorEntityDescription(
        key="battery",
        translation_key="battery voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WeatherFlowSensorEntityDescription(
        key="illuminance",
        translation_key="illuminance",
        native_unit_of_measurement=LIGHT_LUX,
        device_class=SensorDeviceClass.ILLUMINANCE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WeatherFlowSensorEntityDescription(
        key="lightning_strike_average_distance",
        icon="mdi:lightning-bolt",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        suggested_display_precision=2,
    ),
    WeatherFlowSensorEntityDescription(
        key="lightning_strike_count",
        translation_key="lightning_count",
        icon="mdi:lightning-bolt",
        state_class=SensorStateClass.TOTAL,
    ),
    WeatherFlowSensorEntityDescription(
        key="precipitation_type",
        device_class=SensorDeviceClass.ENUM,
        options=[
            "NONE",
            PrecipitationType.NONE,
            PrecipitationType.RAIN,
            PrecipitationType.HAIL,
            PrecipitationType.RAIN_HAIL,
            PrecipitationType.UNKNOWN,
        ],
        icon="mdi:weather-rainy",
    ),
    WeatherFlowSensorEntityDescription(
        key="rain_amount",
        translation_key="rain_amount",
        icon="mdi:weather-rainy",
        native_unit_of_measurement=UnitOfPrecipitationDepth.MILLIMETERS,
        state_class=SensorStateClass.TOTAL,
        device_class=SensorDeviceClass.PRECIPITATION,
        backing_library_attribute="rain_accumulation_previous_minute",
        imperial_suggested_unit=UnitOfPrecipitationDepth.INCHES,
    ),
    WeatherFlowSensorEntityDescription(
        key="rain_rate",
        translation_key="rain_rate",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.PRECIPITATION_INTENSITY,
        icon="mdi:weather-rainy",
        native_unit_of_measurement=UnitOfVolumetricFlux.MILLIMETERS_PER_HOUR,
        # imperial_suggested_unit=UnitOfVolumetricFlux.INCHES_PER_HOUR,
    ),
    WeatherFlowSensorEntityDescription(
        key="relative_humidity",
        translation_key="humidity",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WeatherFlowSensorEntityDescription(
        key="rssi",
        translation_key="rssi",
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        event_subscriptions=[EVENT_STATUS_UPDATE],
    ),
    WeatherFlowSensorEntityDescription(
        key="station_pressure",
        native_unit_of_measurement=UnitOfPressure.MBAR,
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=5,
        imperial_suggested_unit=UnitOfPressure.INHG,
    ),
    WeatherFlowSensorEntityDescription(
        key="solar_radiation",
        native_unit_of_measurement=UnitOfIrradiance.WATTS_PER_SQUARE_METER,
        device_class=SensorDeviceClass.IRRADIANCE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WeatherFlowSensorEntityDescription(
        key="up_since",
        translation_key="up_since",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        event_subscriptions=[EVENT_STATUS_UPDATE],
    ),
    WeatherFlowSensorEntityDescription(
        key="uv",
        translation_key="uv",
        native_unit_of_measurement=UV_INDEX,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WeatherFlowSensorEntityDescription(
        key="vapor_pressure",
        native_unit_of_measurement=UnitOfPressure.MBAR,
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        imperial_suggested_unit=UnitOfPressure.INHG,
        suggested_display_precision=5,
    ),
    ## Wind Sensors
    WeatherFlowWindSensorEntityDescription(
        key="wind_gust",
        translation_key="wind_gust",
        device_class=SensorDeviceClass.WIND_SPEED,
    ),
    WeatherFlowWindSensorEntityDescription(
        key="wind_lull",
        translation_key="wind_lull",
        device_class=SensorDeviceClass.WIND_SPEED,
    ),
    WeatherFlowWindSensorEntityDescription(
        key="wind_speed",
        translation_key="wind_speed",
        device_class=SensorDeviceClass.WIND_SPEED,
        event_subscriptions=[EVENT_RAPID_WIND, EVENT_OBSERVATION],
    ),
    WeatherFlowWindSensorEntityDescription(
        key="wind_speed_average",
        translation_key="wind_speed_average",
        device_class=SensorDeviceClass.WIND_SPEED,
    ),
    WeatherFlowSensorEntityDescription(
        key="wind_direction",
        translation_key="wind_direction",
        icon="mdi:compass-outline",
        native_unit_of_measurement=DEGREE,
        state_class=SensorStateClass.MEASUREMENT,
        event_subscriptions=[EVENT_RAPID_WIND, EVENT_OBSERVATION],
    ),
    WeatherFlowSensorEntityDescription(
        key="wind_direction_average",
        translation_key="wind_direction_average",
        icon="mdi:compass-outline",
        native_unit_of_measurement=DEGREE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up WeatherFlow sensors using config entry."""

    @callback
    def async_add_sensor(device: WeatherFlowDevice) -> None:
        """Add WeatherFlow sensor."""
        LOGGER.debug("Adding sensors for %s", device)

        sensors = [
            WeatherFlowSensorEntity(
                device=device,
                description=description,
                is_metric=(hass.config.units == METRIC_SYSTEM),
            )
            for description in SENSORS
            if (
                description.backing_library_attribute is not None
                and hasattr(device, description.backing_library_attribute)
            )
            or hasattr(device, description.key)
        ]

        custom_sensors = [
            WeatherFlowAirDensitySensorEntity(
                device=device,
                description=description,
                is_metric=(hass.config.units == METRIC_SYSTEM),
            )
            for description in CUSTOM_SENSORS
            if (
                description.backing_library_attribute is not None
                and hasattr(device, description.backing_library_attribute)
            )
            or hasattr(device, description.key)
        ]

        async_add_entities(sensors)
        async_add_entities(custom_sensors)

    config_entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            f"{DOMAIN}_{config_entry.entry_id}_add_{SENSOR_DOMAIN}",
            async_add_sensor,
        )
    )


class WeatherFlowSensorEntity(SensorEntity):
    """Defines a WeatherFlow sensor entity."""

    entity_description: WeatherFlowSensorEntityDescription
    _attr_should_poll = False

    def __init__(
        self,
        device: WeatherFlowDevice,
        description: WeatherFlowSensorEntityDescription,
        is_metric: bool = True,
    ) -> None:
        """Initialize a WeatherFlow sensor entity."""
        self.device = device
        self.entity_description = description

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self.device.serial_number)},
            manufacturer="WeatherFlow",
            model=self.device.model,
            name=f"{self.device.model} {self.device.serial_number}",
            sw_version=self.device.firmware_revision,
            suggested_area="Backyard",
        )
        self._attr_name = f"{self.device.model} {self.device.serial_number} {description.key.replace('_',' ')}"
        self._attr_unique_id = f"{DOMAIN}_{self.device.serial_number}_{description.key}"

        # In the case of the USA - we may want to have a suggested US unit which differs from the internal suggested units
        if (description.imperial_suggested_unit is not None) and (not is_metric):
            self._attr_suggested_unit_of_measurement = (
                description.imperial_suggested_unit
            )

    @property
    def last_reset(self) -> datetime | None:
        """Return the time when the sensor was last reset, if any."""
        if self.entity_description.state_class == SensorStateClass.TOTAL:
            return self.device.last_report
        return None

    @property
    def native_value(self) -> datetime | StateType:
        """Return the state of the sensor."""

        # Extract raw sensor data
        # Either pull from the key (default) or (backing_library_attribute) to get sensor value
        if self.entity_description.backing_library_attribute is not None:
            raw_sensor_data = getattr(
                self.device, self.entity_description.backing_library_attribute
            )
        else:
            raw_sensor_data = getattr(self.device, self.entity_description.key)

        normalized_data = raw_sensor_data

        if isinstance(normalized_data, Quantity):
            sensor_value = normalized_data.magnitude
            return sensor_value
        if isinstance(normalized_data, Enum):
            sensor_value = normalized_data.name
            return sensor_value
        if isinstance(normalized_data, float):
            return normalized_data
        if isinstance(normalized_data, int):
            return normalized_data
        return None

    async def async_added_to_hass(self) -> None:
        """Subscribe to events."""
        for event in self.entity_description.event_subscriptions:
            self.async_on_remove(
                self.device.on(event, lambda _: self.async_write_ha_state())
            )


class WeatherFlowAirDensitySensorEntity(WeatherFlowSensorEntity):
    """Special case where we have a custom function."""

    entity_description: AirDensityWeatherFlowSensorEntityDescription

    def __init__(
        self,
        device: WeatherFlowDevice,
        description: WeatherFlowSensorEntityDescription,
        is_metric: bool = True,
    ) -> None:
        """Initialize the class."""
        super().__init__(device, description, is_metric)
        self.is_metric = is_metric

    @property
    def native_value(self) -> datetime | StateType:
        """Return the state of the sensor - with custom conversion."""
        raw_sensor_data = getattr(self.device, self.entity_description.key)
        # Raw data is in kilograms / cubic meter
        return raw_sensor_data.m * 1000000
