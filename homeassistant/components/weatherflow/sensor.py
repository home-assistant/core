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


IMPERIAL_UNIT_MAP = {
    CONCENTRATION_KILOGRAMS_PER_CUBIC_METER: CONCENTRATION_POUNDS_PER_CUBIC_FOOT,
    UnitOfLength.KILOMETERS: UnitOfLength.MILES,
    UnitOfPrecipitationDepth.MILLIMETERS: UnitOfPrecipitationDepth.INCHES,
    UnitOfVolumetricFlux.MILLIMETERS_PER_HOUR: UnitOfVolumetricFlux.INCHES_PER_HOUR,
    UnitOfPressure.MBAR: UnitOfPressure.INHG,
    UnitOfSpeed.KILOMETERS_PER_HOUR: UnitOfSpeed.MILES_PER_HOUR,
}


@dataclass
class WeatherFlowSensorEntityDescription(SensorEntityDescription):
    """Describes a WeatherFlow sensor entity description."""

    attr: str | None = None
    conversion_fn: Callable[[Quantity], Quantity] | None = None
    decimals: int | None = None
    event_subscriptions: list[str] = field(default_factory=lambda: [EVENT_OBSERVATION])
    value_fn: Callable[[Quantity], Quantity] | None = None


@dataclass
class WeatherFlowTemperatureSensorEntityDescription(WeatherFlowSensorEntityDescription):
    """Describes a WeatherFlow temperature sensor entity description."""

    def __post_init__(self) -> None:
        """Post initialisation processing."""
        self.native_unit_of_measurement = UnitOfTemperature.CELSIUS
        self.device_class = SensorDeviceClass.TEMPERATURE
        self.state_class = SensorStateClass.MEASUREMENT
        self.decimals = 1


@dataclass
class WeatherFlowWindSensorEntityDescription(WeatherFlowSensorEntityDescription):
    """Describes a WeatherFlow wind sensor entity description."""

    def __post_init__(self) -> None:
        """Post initialisation processing."""
        self.icon = "mdi:weather-windy"
        self.native_unit_of_measurement = UnitOfSpeed.KILOMETERS_PER_HOUR
        self.state_class = SensorStateClass.MEASUREMENT
        self.conversion_fn = lambda attr: attr.to(UnitOfSpeed.MILES_PER_HOUR)
        self.decimals = 2
        self.value_fn = lambda attr: attr.to(UnitOfSpeed.KILOMETERS_PER_HOUR)


SENSORS: tuple[WeatherFlowSensorEntityDescription, ...] = (
    WeatherFlowTemperatureSensorEntityDescription(
        key="air_temperature",
        translation_key="temperature",
    ),
    WeatherFlowSensorEntityDescription(
        key="air_density",
        translation_key="air_density",
        native_unit_of_measurement=CONCENTRATION_KILOGRAMS_PER_CUBIC_METER,
        device_class=SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS,
        state_class=SensorStateClass.MEASUREMENT,
        conversion_fn=lambda attr: attr.to(CONCENTRATION_POUNDS_PER_CUBIC_FOOT),
        decimals=5,
    ),
    WeatherFlowTemperatureSensorEntityDescription(
        key="dew_point_temperature",
        translation_key="dew_point",
    ),
    WeatherFlowSensorEntityDescription(
        key="battery",
        translation_key="battery voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WeatherFlowTemperatureSensorEntityDescription(
        key="feels_like_temperature",
        translation_key="feels_like",
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
        translation_key="lightning_average_distance",
        icon="mdi:lightning-bolt",
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        conversion_fn=lambda attr: attr.to(UnitOfLength.MILES),
        decimals=2,
    ),
    WeatherFlowSensorEntityDescription(
        key="lightning_strike_count",
        translation_key="lightning_count",
        icon="mdi:lightning-bolt",
        state_class=SensorStateClass.TOTAL,
    ),
    WeatherFlowSensorEntityDescription(
        key="precipitation_type",
        translation_key="precipitation type",
        icon="mdi:weather-rainy",
    ),
    WeatherFlowSensorEntityDescription(
        key="rain_amount",
        translation_key="rain_amount",
        icon="mdi:weather-rainy",
        native_unit_of_measurement=UnitOfPrecipitationDepth.MILLIMETERS,
        state_class=SensorStateClass.TOTAL,
        attr="rain_accumulation_previous_minute",
        conversion_fn=lambda attr: attr.to(UnitOfPrecipitationDepth.INCHES),
    ),
    WeatherFlowSensorEntityDescription(
        key="rain_rate",
        translation_key="rain_rate",
        icon="mdi:weather-rainy",
        native_unit_of_measurement=UnitOfVolumetricFlux.MILLIMETERS_PER_HOUR,
        attr="rain_rate",
        conversion_fn=lambda attr: attr.to(UnitOfVolumetricFlux.INCHES_PER_HOUR),
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
        translation_key="station_pressure",
        native_unit_of_measurement=UnitOfPressure.MBAR,
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        conversion_fn=lambda attr: attr.to(UnitOfPressure.INHG),
        decimals=5,
    ),
    WeatherFlowSensorEntityDescription(
        key="solar_radiation",
        translation_key="solar_radiation",
        native_unit_of_measurement=UnitOfIrradiance.WATTS_PER_SQUARE_METER,
        device_class=SensorDeviceClass.ILLUMINANCE,
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
        translation_key="vapor_pressure",
        native_unit_of_measurement=UnitOfPressure.MBAR,
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        conversion_fn=lambda attr: attr.to(UnitOfPressure.INHG),
        decimals=5,
    ),
    WeatherFlowTemperatureSensorEntityDescription(
        key="wet_bulb_temperature",
        translation_key="wet_bulb_temperature",
    ),
    WeatherFlowWindSensorEntityDescription(
        key="wind_speed_average",
        translation_key="wind_speed_average",
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
    WeatherFlowWindSensorEntityDescription(
        key="wind_gust",
        translation_key="wind_gust",
    ),
    WeatherFlowWindSensorEntityDescription(
        key="wind_lull",
        translation_key="wind_lull",
    ),
    WeatherFlowWindSensorEntityDescription(
        key="wind_speed",
        translation_key="wind_speed",
        event_subscriptions=[EVENT_RAPID_WIND, EVENT_OBSERVATION],
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
                is_metric=hass.config.units is METRIC_SYSTEM,
            )
            for description in SENSORS
            if hasattr(
                device,
                description.key if description.attr is None else description.attr,
            )
        ]
        for sensor in sensors:
            LOGGER.debug(
                "Adding %s [%s]", sensor.name, sensor.native_unit_of_measurement
            )

        async_add_entities(sensors)

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
        if not is_metric and (
            (unit := IMPERIAL_UNIT_MAP.get(description.native_unit_of_measurement))  # type: ignore[arg-type]
            is not None
        ):
            description.native_unit_of_measurement = unit
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
        raw_sensor_data = getattr(
            self.device,
            self.entity_description.key
            if self.entity_description.attr is None
            else self.entity_description.attr,
        )

        if raw_sensor_data is None:
            return raw_sensor_data

        # Utilize the internal conversion of pyweatherudp to extract correct sensor values
        if (
            self.hass.config.units is not METRIC_SYSTEM
            and (function := self.entity_description.conversion_fn) is not None
        ) or (function := self.entity_description.value_fn) is not None:
            noramlized_sensor_data = function(raw_sensor_data)
        else:
            noramlized_sensor_data = raw_sensor_data

        if isinstance(noramlized_sensor_data, Quantity):
            sensor_value = noramlized_sensor_data.magnitude
            if (decimals := self.entity_description.decimals) is not None:
                sensor_value = round(sensor_value, decimals)
            return sensor_value

        if isinstance(noramlized_sensor_data, Enum):
            sensor_value = noramlized_sensor_data.name

        return sensor_value

    async def async_added_to_hass(self) -> None:
        """Subscribe to events."""
        for event in self.entity_description.event_subscriptions:
            self.async_on_remove(
                self.device.on(event, lambda _: self.async_write_ha_state())
            )
