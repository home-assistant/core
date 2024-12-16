"""Support for Watergate sensors."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
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

from . import WatergateConfigEntry
from .coordinator import WatergateAgregatedRequests, WatergateDataCoordinator
from .entity import WatergateEntity

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


@dataclass(kw_only=True, frozen=True)
class WatergateSensorEntityDescription(SensorEntityDescription):
    """Description for Watergate sensor entities."""

    value_fn: Callable[[WatergateAgregatedRequests], str | int | float | None]


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
        value_fn=lambda data: data.networking.wifi_uptime if data.networking else None,
        translation_key="wifi_uptime",
        key="wifi_uptime",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        native_unit_of_measurement=UnitOfTime.MILLISECONDS,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    WatergateSensorEntityDescription(
        value_fn=lambda data: data.networking.mqtt_uptime if data.networking else None,
        translation_key="mqtt_uptime",
        key="mqtt_uptime",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        native_unit_of_measurement=UnitOfTime.MILLISECONDS,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL_INCREASING,
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
        value_fn=lambda data: data.state.uptime if data.state else None,
        translation_key="uptime",
        key="uptime",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL_INCREASING,
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

    entities: list[SensorEntity] = [
        SonicSensor(coordinator, description) for description in DESCRIPTIONS
    ]

    entities.extend([AutoShutOffEventSensor(coordinator)])

    async_add_entities(entities)


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

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle data update."""
        self._attr_native_value = self.entity_description.value_fn(
            self.coordinator.data
        )
        self._attr_available = self._attr_native_value is not None
        self.async_write_ha_state()


class AutoShutOffEventSensor(WatergateEntity, SensorEntity):
    """Representation of a sensor showing the latest long flow event."""

    def __init__(
        self,
        coordinator: WatergateDataCoordinator,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, "auto_shut_off_event")
        self.entity_description = SensorEntityDescription(
            key="auto_shut_off_event",
            translation_key="auto_shut_off_event",
            device_class=SensorDeviceClass.TIMESTAMP,
        )

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return (
            super().available and self.coordinator.data.auto_shut_off_report is not None
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle data update."""
        if self.coordinator.last_update_success and (
            data := self.coordinator.data.auto_shut_off_report
        ):
            self._attr_native_value = datetime.fromtimestamp(data.timestamp, UTC)
            self._attr_extra_state_attributes = {
                "type": data.type,
                "duration": data.duration,
                "volume": data.volume,
            }
            self.async_write_ha_state()
