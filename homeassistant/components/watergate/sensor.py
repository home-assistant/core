"""Support for Watergate sensors."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
import logging

from watergate_local_api.models import AutoShutOffReport

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

ASO_EVENT_TYPE_ATRIBUTE = "type"
ASO_EVENT_VOLUME_ATRIBUTE = "volume"
ASO_EVENT_DURATION_ATRIBUTE = "duration"

UPTIME_ENTITY_NAME = "uptime"
POWER_SUPPLY_ENTITY_NAME = "power_supply"
PRESSURE_ENTITY_NAME = "water_pressure"
TEMPERATURE_ENTITY_NAME = "water_temperature"
FLOW_ENTITY_NAME = "water_flow_rate"
IP_ENTITY_NAME = "ip"
GATEWAY_ENTITY_NAME = "gateway"
SUBNET_ENTITY_NAME = "subnet"
SSID_ENTITY_NAME = "ssid"
RSSI_ENTITY_NAME = "rssi"
WIFI_UPTIME_ENTITY_NAME = "wifi_uptime"
MQTT_UPTIME_ENTITY_NAME = "mqtt_uptime"
SHUT_OFF_EVENT_ENTITY_NAME = "auto_shut_off_event"
WATER_METER_VOLUME_ENTITY_NAME = "water_meter_volume"
WATER_METER_DURATION_ENTITY_NAME = "water_meter_duration"


@dataclass(kw_only=True, frozen=True)
class WatergateSensorEntityDescription(SensorEntityDescription):
    """Description for Acaia sensor entities."""

    value_fn: Callable[[WatergateAgregatedRequests], str | int | float | None]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: WatergateConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up all entries for Watergate Platform."""

    coordinator = config_entry.runtime_data

    descriptions: list[WatergateSensorEntityDescription] = [
        WatergateSensorEntityDescription(
            value_fn=lambda data: data.state.water_meter.duration
            if data.state and data.state.water_meter
            else None,
            translation_key=WATER_METER_VOLUME_ENTITY_NAME,
            key=WATER_METER_VOLUME_ENTITY_NAME,
            native_unit_of_measurement=UnitOfVolume.LITERS,
            device_class=SensorDeviceClass.WATER,
            state_class=SensorStateClass.TOTAL_INCREASING,
        ),
        WatergateSensorEntityDescription(
            value_fn=lambda data: data.state.water_meter.duration
            if data.state and data.state.water_meter
            else None,
            name=WATER_METER_DURATION_ENTITY_NAME,
            key=WATER_METER_DURATION_ENTITY_NAME,
            native_unit_of_measurement=UnitOfTime.MINUTES,
            device_class=SensorDeviceClass.DURATION,
        ),
        WatergateSensorEntityDescription(
            value_fn=lambda data: data.networking.ip if data.networking else None,
            name=IP_ENTITY_NAME,
            key=IP_ENTITY_NAME,
            entity_category=EntityCategory.DIAGNOSTIC,
            entity_registry_enabled_default=False,
        ),
        WatergateSensorEntityDescription(
            value_fn=lambda data: data.networking.gateway if data.networking else None,
            name=GATEWAY_ENTITY_NAME,
            key=GATEWAY_ENTITY_NAME,
            entity_category=EntityCategory.DIAGNOSTIC,
            entity_registry_enabled_default=False,
        ),
        WatergateSensorEntityDescription(
            value_fn=lambda data: data.networking.subnet if data.networking else None,
            name=SUBNET_ENTITY_NAME,
            key=SUBNET_ENTITY_NAME,
            entity_category=EntityCategory.DIAGNOSTIC,
            entity_registry_enabled_default=False,
        ),
        WatergateSensorEntityDescription(
            value_fn=lambda data: data.networking.ssid if data.networking else None,
            name=SSID_ENTITY_NAME,
            key=SSID_ENTITY_NAME,
            entity_category=EntityCategory.DIAGNOSTIC,
            entity_registry_enabled_default=False,
        ),
        WatergateSensorEntityDescription(
            value_fn=lambda data: data.networking.rssi if data.networking else None,
            name=RSSI_ENTITY_NAME,
            key=RSSI_ENTITY_NAME,
            entity_category=EntityCategory.DIAGNOSTIC,
            entity_registry_enabled_default=False,
            native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
            device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        ),
        WatergateSensorEntityDescription(
            value_fn=lambda data: data.networking.wifi_uptime
            if data.networking
            else None,
            name=WIFI_UPTIME_ENTITY_NAME,
            key=WIFI_UPTIME_ENTITY_NAME,
            entity_category=EntityCategory.DIAGNOSTIC,
            entity_registry_enabled_default=False,
            native_unit_of_measurement=UnitOfTime.MILLISECONDS,
            device_class=SensorDeviceClass.DURATION,
        ),
        WatergateSensorEntityDescription(
            value_fn=lambda data: data.networking.mqtt_uptime
            if data.networking
            else None,
            name=MQTT_UPTIME_ENTITY_NAME,
            key=MQTT_UPTIME_ENTITY_NAME,
            entity_category=EntityCategory.DIAGNOSTIC,
            entity_registry_enabled_default=False,
            native_unit_of_measurement=UnitOfTime.MILLISECONDS,
            device_class=SensorDeviceClass.DURATION,
        ),
        WatergateSensorEntityDescription(
            value_fn=lambda data: data.telemetry.water_temperature
            if data.telemetry
            else None,
            name=TEMPERATURE_ENTITY_NAME,
            key=TEMPERATURE_ENTITY_NAME,
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
            device_class=SensorDeviceClass.TEMPERATURE,
        ),
        WatergateSensorEntityDescription(
            value_fn=lambda data: data.telemetry.pressure if data.telemetry else None,
            name=PRESSURE_ENTITY_NAME,
            key=PRESSURE_ENTITY_NAME,
            native_unit_of_measurement=UnitOfPressure.MBAR,
            device_class=SensorDeviceClass.PRESSURE,
        ),
        WatergateSensorEntityDescription(
            value_fn=lambda data: (data.telemetry.flow / 1000)
            if (data.telemetry and data.telemetry.flow is not None)
            else None,
            name=FLOW_ENTITY_NAME,
            key=FLOW_ENTITY_NAME,
            native_unit_of_measurement=UnitOfVolumeFlowRate.LITERS_PER_MINUTE,
            device_class=SensorDeviceClass.VOLUME_FLOW_RATE,
        ),
        WatergateSensorEntityDescription(
            value_fn=lambda data: data.state.uptime if data.state else None,
            name=UPTIME_ENTITY_NAME,
            key=UPTIME_ENTITY_NAME,
            entity_category=EntityCategory.DIAGNOSTIC,
            entity_registry_enabled_default=False,
            native_unit_of_measurement=UnitOfTime.SECONDS,
            device_class=SensorDeviceClass.DURATION,
        ),
        WatergateSensorEntityDescription(
            value_fn=lambda data: data.state.power_supply if data.state else None,
            name=POWER_SUPPLY_ENTITY_NAME,
            key=POWER_SUPPLY_ENTITY_NAME,
            entity_category=EntityCategory.DIAGNOSTIC,
            entity_registry_enabled_default=False,
        ),
    ]

    entities: list[SensorEntity] = [
        SonicSensor(coordinator, description) for description in descriptions
    ]
    entities.extend([AutoShutOffEventSensor(coordinator)])

    async_add_entities(entities, True)


class SonicSensor(WatergateEntity, SensorEntity):
    """Define a Sonic Sensor entity."""

    _attr_has_entity_name = True
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

    def update(self, value: str | None) -> None:
        """Update the sensor."""
        self._attr_native_value = value
        self.async_write_ha_state()


class AutoShutOffEventSensor(WatergateEntity, SensorEntity):
    """Representation of a sensor showing the latest long flow event."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: WatergateDataCoordinator,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, SHUT_OFF_EVENT_ENTITY_NAME)
        self.entity_description = SensorEntityDescription(
            key=SHUT_OFF_EVENT_ENTITY_NAME,
            translation_key=SHUT_OFF_EVENT_ENTITY_NAME,
            device_class=SensorDeviceClass.TIMESTAMP,
        )

    def update(self, report: AutoShutOffReport) -> None:
        """Update the sensor."""
        self._attr_native_value = datetime.fromtimestamp(report.timestamp, UTC)
        self._attr_extra_state_attributes = {
            ASO_EVENT_TYPE_ATRIBUTE: report.type,
            ASO_EVENT_DURATION_ATRIBUTE: report.duration,
            ASO_EVENT_VOLUME_ATRIBUTE: report.volume,
        }
        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return (
            super().available and self.coordinator.data.auto_shut_off_report is not None
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle data update."""
        if self.coordinator.last_update_success:
            data = self.coordinator.data.auto_shut_off_report
            if data:
                self.update(data)
