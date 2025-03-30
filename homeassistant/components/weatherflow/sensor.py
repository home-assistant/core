"""Sensors for the weatherflow integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from pyweatherflowudp.const import EVENT_RAPID_WIND
from pyweatherflowudp.device import (
    EVENT_OBSERVATION,
    EVENT_STATUS_UPDATE,
    WeatherFlowDevice,
)

from homeassistant.components.sensor import (
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
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.util.unit_system import METRIC_SYSTEM

from .const import DOMAIN, LOGGER, format_dispatch_call


def precipitation_raw_conversion_fn(raw_data: Enum):
    """Parse parse precipitation type."""
    if raw_data.name.lower() == "unknown":
        return None
    return raw_data.name.lower()


@dataclass(frozen=True, kw_only=True)
class WeatherFlowSensorEntityDescription(SensorEntityDescription):
    """Describes WeatherFlow sensor entity."""

    raw_data_conv_fn: Callable[[WeatherFlowDevice], datetime | StateType]

    event_subscriptions: list[str] = field(default_factory=lambda: [EVENT_OBSERVATION])
    imperial_suggested_unit: str | None = None

    def get_native_value(self, device: WeatherFlowDevice) -> datetime | StateType:
        """Return the parsed sensor value."""
        if (raw_sensor_data := getattr(device, self.key)) is None:
            return None
        return self.raw_data_conv_fn(raw_sensor_data)


SENSORS: tuple[WeatherFlowSensorEntityDescription, ...] = (
    WeatherFlowSensorEntityDescription(
        key="air_density",
        translation_key="air_density",
        native_unit_of_measurement="kg/m³",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=5,
        raw_data_conv_fn=lambda raw_data: raw_data.magnitude,
    ),
    WeatherFlowSensorEntityDescription(
        key="air_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        raw_data_conv_fn=lambda raw_data: raw_data.magnitude,
    ),
    WeatherFlowSensorEntityDescription(
        key="dew_point_temperature",
        translation_key="dew_point",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        raw_data_conv_fn=lambda raw_data: raw_data.magnitude,
    ),
    WeatherFlowSensorEntityDescription(
        key="feels_like_temperature",
        translation_key="feels_like",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        raw_data_conv_fn=lambda raw_data: raw_data.magnitude,
    ),
    WeatherFlowSensorEntityDescription(
        key="wet_bulb_temperature",
        translation_key="wet_bulb_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        raw_data_conv_fn=lambda raw_data: raw_data.magnitude,
    ),
    WeatherFlowSensorEntityDescription(
        key="battery",
        translation_key="battery_voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        raw_data_conv_fn=lambda raw_data: raw_data.magnitude,
    ),
    WeatherFlowSensorEntityDescription(
        key="illuminance",
        native_unit_of_measurement=LIGHT_LUX,
        device_class=SensorDeviceClass.ILLUMINANCE,
        state_class=SensorStateClass.MEASUREMENT,
        raw_data_conv_fn=lambda raw_data: raw_data.magnitude,
    ),
    WeatherFlowSensorEntityDescription(
        key="lightning_strike_average_distance",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        translation_key="lightning_average_distance",
        suggested_display_precision=2,
        raw_data_conv_fn=lambda raw_data: raw_data.magnitude,
    ),
    WeatherFlowSensorEntityDescription(
        key="lightning_strike_count",
        translation_key="lightning_count",
        state_class=SensorStateClass.TOTAL,
        raw_data_conv_fn=lambda raw_data: raw_data,
    ),
    WeatherFlowSensorEntityDescription(
        key="precipitation_type",
        translation_key="precipitation_type",
        device_class=SensorDeviceClass.ENUM,
        options=["none", "rain", "hail", "rain_hail", "unknown"],
        raw_data_conv_fn=precipitation_raw_conversion_fn,
    ),
    WeatherFlowSensorEntityDescription(
        key="rain_accumulation_previous_minute",
        native_unit_of_measurement=UnitOfPrecipitationDepth.MILLIMETERS,
        state_class=SensorStateClass.TOTAL,
        device_class=SensorDeviceClass.PRECIPITATION,
        imperial_suggested_unit=UnitOfPrecipitationDepth.INCHES,
        raw_data_conv_fn=lambda raw_data: raw_data.magnitude,
    ),
    WeatherFlowSensorEntityDescription(
        key="rain_rate",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.PRECIPITATION_INTENSITY,
        native_unit_of_measurement=UnitOfVolumetricFlux.MILLIMETERS_PER_HOUR,
        raw_data_conv_fn=lambda raw_data: raw_data.magnitude,
    ),
    WeatherFlowSensorEntityDescription(
        key="relative_humidity",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        raw_data_conv_fn=lambda raw_data: raw_data.magnitude,
    ),
    WeatherFlowSensorEntityDescription(
        key="rssi",
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        event_subscriptions=[EVENT_STATUS_UPDATE],
        raw_data_conv_fn=lambda raw_data: raw_data.magnitude,
    ),
    WeatherFlowSensorEntityDescription(
        key="station_pressure",
        translation_key="station_pressure",
        native_unit_of_measurement=UnitOfPressure.MBAR,
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=5,
        imperial_suggested_unit=UnitOfPressure.INHG,
        raw_data_conv_fn=lambda raw_data: raw_data.magnitude,
    ),
    WeatherFlowSensorEntityDescription(
        key="solar_radiation",
        native_unit_of_measurement=UnitOfIrradiance.WATTS_PER_SQUARE_METER,
        device_class=SensorDeviceClass.IRRADIANCE,
        state_class=SensorStateClass.MEASUREMENT,
        raw_data_conv_fn=lambda raw_data: raw_data.magnitude,
    ),
    WeatherFlowSensorEntityDescription(
        key="up_since",
        translation_key="uptime",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        event_subscriptions=[EVENT_STATUS_UPDATE],
        raw_data_conv_fn=lambda raw_data: raw_data,
    ),
    WeatherFlowSensorEntityDescription(
        key="uv",
        translation_key="uv_index",
        native_unit_of_measurement=UV_INDEX,
        state_class=SensorStateClass.MEASUREMENT,
        raw_data_conv_fn=lambda raw_data: raw_data,
    ),
    WeatherFlowSensorEntityDescription(
        key="vapor_pressure",
        translation_key="vapor_pressure",
        native_unit_of_measurement=UnitOfPressure.MBAR,
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        imperial_suggested_unit=UnitOfPressure.INHG,
        suggested_display_precision=5,
        raw_data_conv_fn=lambda raw_data: raw_data.magnitude,
    ),
    ## Wind Sensors
    WeatherFlowSensorEntityDescription(
        key="wind_gust",
        translation_key="wind_gust",
        device_class=SensorDeviceClass.WIND_SPEED,
        native_unit_of_measurement=UnitOfSpeed.METERS_PER_SECOND,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        raw_data_conv_fn=lambda raw_data: raw_data.magnitude,
    ),
    WeatherFlowSensorEntityDescription(
        key="wind_lull",
        translation_key="wind_lull",
        device_class=SensorDeviceClass.WIND_SPEED,
        native_unit_of_measurement=UnitOfSpeed.METERS_PER_SECOND,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        raw_data_conv_fn=lambda raw_data: raw_data.magnitude,
    ),
    WeatherFlowSensorEntityDescription(
        key="wind_speed",
        device_class=SensorDeviceClass.WIND_SPEED,
        event_subscriptions=[EVENT_RAPID_WIND, EVENT_OBSERVATION],
        native_unit_of_measurement=UnitOfSpeed.METERS_PER_SECOND,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        raw_data_conv_fn=lambda raw_data: raw_data.magnitude,
    ),
    WeatherFlowSensorEntityDescription(
        key="wind_average",
        translation_key="wind_speed_average",
        device_class=SensorDeviceClass.WIND_SPEED,
        native_unit_of_measurement=UnitOfSpeed.METERS_PER_SECOND,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        raw_data_conv_fn=lambda raw_data: raw_data.magnitude,
    ),
    WeatherFlowSensorEntityDescription(
        key="wind_direction",
        translation_key="wind_direction",
        device_class=SensorDeviceClass.WIND_DIRECTION,
        state_class=SensorStateClass.MEASUREMENT_ANGLE,
        native_unit_of_measurement=DEGREE,
        event_subscriptions=[EVENT_RAPID_WIND, EVENT_OBSERVATION],
        raw_data_conv_fn=lambda raw_data: raw_data.magnitude,
    ),
    WeatherFlowSensorEntityDescription(
        key="wind_direction_average",
        translation_key="wind_direction_average",
        device_class=SensorDeviceClass.WIND_DIRECTION,
        native_unit_of_measurement=DEGREE,
        raw_data_conv_fn=lambda raw_data: raw_data.magnitude,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up WeatherFlow sensors using config entry."""

    @callback
    def async_add_sensor(device: WeatherFlowDevice) -> None:
        """Add WeatherFlow sensor."""
        LOGGER.debug("Adding sensors for %s", device)

        sensors: list[WeatherFlowSensorEntity] = [
            WeatherFlowSensorEntity(
                device=device,
                description=description,
                is_metric=(hass.config.units == METRIC_SYSTEM),
            )
            for description in SENSORS
            if hasattr(device, description.key)
        ]

        async_add_entities(sensors)

    config_entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            format_dispatch_call(config_entry),
            async_add_sensor,
        )
    )


class WeatherFlowSensorEntity(SensorEntity):
    """Defines a WeatherFlow sensor entity."""

    entity_description: WeatherFlowSensorEntityDescription
    _attr_should_poll = False
    _attr_has_entity_name = True

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
            identifiers={(DOMAIN, device.serial_number)},
            manufacturer="WeatherFlow",
            model=device.model,
            name=device.serial_number,
            sw_version=device.firmware_revision,
        )

        self._attr_unique_id = f"{device.serial_number}_{description.key}"

        # In the case of the USA - we may want to have a suggested US unit which differs from the internal suggested units
        if description.imperial_suggested_unit is not None and not is_metric:
            self._attr_suggested_unit_of_measurement = (
                description.imperial_suggested_unit
            )

    @property
    def last_reset(self) -> datetime | None:
        """Return the time when the sensor was last reset, if any."""
        if self.entity_description.state_class == SensorStateClass.TOTAL:
            return self.device.last_report
        return None

    def _async_update_state(self) -> None:
        """Update entity state."""
        value = self.entity_description.get_native_value(self.device)
        self._attr_available = value is not None
        self._attr_native_value = value
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Subscribe to events."""
        self._async_update_state()
        for event in self.entity_description.event_subscriptions:
            self.async_on_remove(
                self.device.on(event, lambda _: self._async_update_state())
            )
