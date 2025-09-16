"""Support for the VRM Solar Forecast sensor service."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import (
    VictronRemoteMonitoringConfigEntry,
    VictronRemoteMonitoringDataUpdateCoordinator,
    VRMForecastStore,
)


@dataclass(frozen=True, kw_only=True)
class VRMForecastsSensorEntityDescription(SensorEntityDescription):
    """Describes a VRM Forecast Sensor."""

    state: Callable[[VRMForecastStore], Any]


SENSORS: tuple[VRMForecastsSensorEntityDescription, ...] = (
    # Solar forecast sensors
    VRMForecastsSensorEntityDescription(
        key="energy_production_estimate_yesterday",
        translation_key="energy_production_estimate_yesterday",
        state=lambda estimate: estimate.solar.yesterday_total,
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=1,
    ),
    VRMForecastsSensorEntityDescription(
        key="energy_production_estimate_today",
        translation_key="energy_production_estimate_today",
        state=lambda estimate: estimate.solar.today_total,
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=1,
    ),
    VRMForecastsSensorEntityDescription(
        key="energy_production_estimate_today_remaining",
        translation_key="energy_production_estimate_today_remaining",
        state=lambda estimate: estimate.solar.today_left_total,
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=1,
    ),
    VRMForecastsSensorEntityDescription(
        key="energy_production_estimate_tomorrow",
        translation_key="energy_production_estimate_tomorrow",
        state=lambda estimate: estimate.solar.tomorrow_total,
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=1,
    ),
    VRMForecastsSensorEntityDescription(
        key="power_highest_peak_time_yesterday",
        translation_key="power_highest_peak_time_yesterday",
        state=lambda estimate: estimate.solar.yesterday_peak_time,
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    VRMForecastsSensorEntityDescription(
        key="power_highest_peak_time_today",
        translation_key="power_highest_peak_time_today",
        state=lambda estimate: estimate.solar.today_peak_time,
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    VRMForecastsSensorEntityDescription(
        key="power_highest_peak_time_tomorrow",
        translation_key="power_highest_peak_time_tomorrow",
        state=lambda estimate: estimate.solar.tomorrow_peak_time,
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    VRMForecastsSensorEntityDescription(
        key="energy_production_current_hour",
        translation_key="energy_production_current_hour",
        state=lambda estimate: estimate.solar.current_hour_total,
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=1,
    ),
    VRMForecastsSensorEntityDescription(
        key="energy_production_next_hour",
        translation_key="energy_production_next_hour",
        state=lambda estimate: estimate.solar.next_hour_total,
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=1,
    ),
    # Consumption forecast sensors
    VRMForecastsSensorEntityDescription(
        key="energy_consumption_estimate_yesterday",
        translation_key="energy_consumption_estimate_yesterday",
        state=lambda estimate: estimate.consumption.yesterday_total,
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=1,
    ),
    VRMForecastsSensorEntityDescription(
        key="energy_consumption_estimate_today",
        translation_key="energy_consumption_estimate_today",
        state=lambda estimate: estimate.consumption.today_total,
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=1,
    ),
    VRMForecastsSensorEntityDescription(
        key="energy_consumption_estimate_today_remaining",
        translation_key="energy_consumption_estimate_today_remaining",
        state=lambda estimate: estimate.consumption.today_left_total,
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=1,
    ),
    VRMForecastsSensorEntityDescription(
        key="energy_consumption_estimate_tomorrow",
        translation_key="energy_consumption_estimate_tomorrow",
        state=lambda estimate: estimate.consumption.tomorrow_total,
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=1,
    ),
    VRMForecastsSensorEntityDescription(
        key="consumption_highest_peak_time_yesterday",
        translation_key="consumption_highest_peak_time_yesterday",
        state=lambda estimate: estimate.consumption.yesterday_peak_time,
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    VRMForecastsSensorEntityDescription(
        key="consumption_highest_peak_time_today",
        translation_key="consumption_highest_peak_time_today",
        state=lambda estimate: estimate.consumption.today_peak_time,
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    VRMForecastsSensorEntityDescription(
        key="consumption_highest_peak_time_tomorrow",
        translation_key="consumption_highest_peak_time_tomorrow",
        state=lambda estimate: estimate.consumption.tomorrow_peak_time,
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    VRMForecastsSensorEntityDescription(
        key="energy_consumption_current_hour",
        translation_key="energy_consumption_current_hour",
        state=lambda estimate: estimate.consumption.current_hour_total,
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=1,
    ),
    VRMForecastsSensorEntityDescription(
        key="energy_consumption_next_hour",
        translation_key="energy_consumption_next_hour",
        state=lambda estimate: estimate.consumption.next_hour_total,
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=1,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VictronRemoteMonitoringConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Defer sensor setup to the shared sensor module."""
    coordinator = entry.runtime_data

    async_add_entities(
        VRMForecastsSensorEntity(
            entry_id=entry.entry_id,
            coordinator=coordinator,
            description=entity_description,
        )
        for entity_description in SENSORS
    )


class VRMForecastsSensorEntity(
    CoordinatorEntity[VictronRemoteMonitoringDataUpdateCoordinator], SensorEntity
):
    """Defines a VRM Solar Forecast sensor."""

    entity_description: VRMForecastsSensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        *,
        entry_id: str,
        coordinator: VictronRemoteMonitoringDataUpdateCoordinator,
        description: VRMForecastsSensorEntityDescription,
    ) -> None:
        """Initialize VRM Solar Forecast sensor."""
        super().__init__(coordinator=coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{description.key}_{coordinator.data.site_id}"

        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, str(coordinator.data.site_id))},
            manufacturer="Victron Energy",
            model=f"VRM - {coordinator.data.site_id}",
            name="Victron Remote Monitoring",
            configuration_url="https://vrm.victronenergy.com",
        )

    @property
    def native_value(self) -> datetime | StateType:
        """Return the state of the sensor."""
        return self.entity_description.state(self.coordinator.data)
