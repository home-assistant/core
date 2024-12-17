"""Support for Watergate sensors."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging

from homeassistant.components.sensor import (
    HomeAssistant,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfPressure,
    UnitOfTemperature,
    UnitOfTime,
    UnitOfVolume,
    UnitOfVolumeFlowRate,
)
from homeassistant.core import callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from . import WatergateConfigEntry
from .coordinator import WatergateAgregatedRequests, WatergateDataCoordinator
from .entity import WatergateEntity

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


@dataclass(kw_only=True, frozen=True)
class WatergateSensorEntityDescription(SensorEntityDescription):
    """Description for Watergate sensor entities."""

    value_fn: Callable[
        [WatergateAgregatedRequests], str | int | float | datetime | None
    ]


DESCRIPTIONS: list[WatergateSensorEntityDescription] = [
    WatergateSensorEntityDescription(
        value_fn=lambda data: data.state.water_meter.duration
        if data.state and data.state.water_meter
        else None,
        translation_key="water_meter_volume",
        key="water_meter_volume",
        native_unit_of_measurement=UnitOfVolume.LITERS,
        device_class=SensorDeviceClass.WATER,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    WatergateSensorEntityDescription(
        value_fn=lambda data: data.state.water_meter.duration
        if data.state and data.state.water_meter
        else None,
        translation_key="water_meter_duration",
        key="water_meter_duration",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    WatergateSensorEntityDescription(
        value_fn=lambda data: data.networking.ip if data.networking else None,
        translation_key="ip",
        key="ip",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    WatergateSensorEntityDescription(
        value_fn=lambda data: data.networking.gateway if data.networking else None,
        translation_key="gateway",
        key="gateway",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    WatergateSensorEntityDescription(
        value_fn=lambda data: data.networking.subnet if data.networking else None,
        translation_key="subnet",
        key="subnet",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    WatergateSensorEntityDescription(
        value_fn=lambda data: data.networking.ssid if data.networking else None,
        translation_key="ssid",
        key="ssid",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    WatergateSensorEntityDescription(
        value_fn=lambda data: data.networking.rssi if data.networking else None,
        translation_key="rssi",
        key="rssi",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WatergateSensorEntityDescription(
        value_fn=lambda data: dt_util.as_utc(
            dt_util.now() - timedelta(microseconds=data.networking.wifi_uptime)
        )
        if data.networking
        else None,
        translation_key="wifi_uptime",
        key="wifi_uptime",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    WatergateSensorEntityDescription(
        value_fn=lambda data: dt_util.as_utc(
            dt_util.now() - timedelta(microseconds=data.networking.mqtt_uptime)
        )
        if data.networking
        else None,
        translation_key="mqtt_uptime",
        key="mqtt_uptime",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    WatergateSensorEntityDescription(
        value_fn=lambda data: data.telemetry.water_temperature
        if data.telemetry
        else None,
        translation_key="water_temperature",
        key="water_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WatergateSensorEntityDescription(
        value_fn=lambda data: data.telemetry.pressure if data.telemetry else None,
        translation_key="water_pressure",
        key="water_pressure",
        native_unit_of_measurement=UnitOfPressure.MBAR,
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WatergateSensorEntityDescription(
        value_fn=lambda data: (data.telemetry.flow / 1000)
        if (data.telemetry and data.telemetry.flow is not None)
        else None,
        translation_key="water_flow_rate",
        key="water_flow_rate",
        native_unit_of_measurement=UnitOfVolumeFlowRate.LITERS_PER_MINUTE,
        device_class=SensorDeviceClass.VOLUME_FLOW_RATE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WatergateSensorEntityDescription(
        value_fn=lambda data: dt_util.as_utc(
            dt_util.now() - timedelta(seconds=data.state.uptime)
        )
        if data.state
        else None,
        translation_key="uptime",
        key="uptime",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    WatergateSensorEntityDescription(
        value_fn=lambda data: data.state.power_supply if data.state else None,
        translation_key="power_supply",
        key="power_supply",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: WatergateConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up all entries for Watergate Platform."""

    coordinator = config_entry.runtime_data

    async_add_entities(
        SonicSensor(coordinator, description) for description in DESCRIPTIONS
    )


class SonicSensor(WatergateEntity, SensorEntity):
    """Define a Sonic Sensor entity."""

    entity_description: WatergateSensorEntityDescription

    def __init__(
        self,
        coordinator: WatergateDataCoordinator,
        entity_description: WatergateSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entity_description.key)
        self.entity_description = entity_description

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return (
            super().available
            and self.entity_description.value_fn(self.coordinator.data) is not None
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle data update."""
        self._attr_native_value = self.entity_description.value_fn(
            self.coordinator.data
        )
        self.async_write_ha_state()
