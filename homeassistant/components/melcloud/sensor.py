"""Support for MelCloud device sensors."""

from __future__ import annotations

from collections.abc import Callable
import dataclasses
from typing import Any

from pymelcloud import DEVICE_TYPE_ATA, DEVICE_TYPE_ATW
from pymelcloud.atw_device import Zone

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import MelCloudConfigEntry, MelCloudDeviceUpdateCoordinator
from .entity import MelCloudEntity


@dataclasses.dataclass(frozen=True, kw_only=True)
class MelcloudSensorEntityDescription(SensorEntityDescription):
    """Describes Melcloud sensor entity."""

    value_fn: Callable[[Any], float | None]
    enabled: Callable[[Any], bool]


ATA_SENSORS: tuple[MelcloudSensorEntityDescription, ...] = (
    MelcloudSensorEntityDescription(
        key="room_temperature",
        translation_key="room_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.device.room_temperature,
        enabled=lambda data: True,
    ),
    MelcloudSensorEntityDescription(
        key="energy",
        translation_key="energy_consumed",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: data.device.total_energy_consumed,
        enabled=lambda data: data.device.has_energy_consumed_meter,
    ),
    MelcloudSensorEntityDescription(
        key="outside_temperature",
        translation_key="outside_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.device.outdoor_temperature,
        enabled=lambda data: data.device.has_outdoor_temperature,
    ),
)
ATW_SENSORS: tuple[MelcloudSensorEntityDescription, ...] = (
    MelcloudSensorEntityDescription(
        key="outside_temperature",
        translation_key="outside_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.device.outside_temperature,
        enabled=lambda data: True,
    ),
    MelcloudSensorEntityDescription(
        key="tank_temperature",
        translation_key="tank_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.device.tank_temperature,
        enabled=lambda data: True,
    ),
    MelcloudSensorEntityDescription(
        key="system_flow_temperature",
        translation_key="flow_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: data.device.flow_temperature,
        enabled=lambda data: data.device.flow_temperature is not None,
    ),
    MelcloudSensorEntityDescription(
        key="system_return_temperature",
        translation_key="return_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: data.device.return_temperature,
        enabled=lambda data: data.device.return_temperature is not None,
    ),
    MelcloudSensorEntityDescription(
        key="flow_temperature_boiler",
        translation_key="flow_temperature_boiler",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: data.device.flow_temperature_boiler,
        enabled=lambda data: data.device.flow_temperature_boiler is not None,
    ),
    MelcloudSensorEntityDescription(
        key="return_temperature_boiler",
        translation_key="return_temperature_boiler",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: data.device.return_temperature_boiler,
        enabled=lambda data: data.device.return_temperature_boiler is not None,
    ),
    MelcloudSensorEntityDescription(
        key="mixing_tank_temperature",
        translation_key="mixing_tank_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: data.device.mixing_tank_temperature,
        enabled=lambda data: data.device.mixing_tank_temperature is not None,
    ),
    MelcloudSensorEntityDescription(
        key="condensing_temperature",
        translation_key="condensing_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: data.device.condensing_temperature,
        enabled=lambda data: True,
    ),
    MelcloudSensorEntityDescription(
        key="fan_frequency",
        translation_key="fan_frequency",
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.device.heat_pump_frequency,
        enabled=lambda data: True,
    ),
    MelcloudSensorEntityDescription(
        key="demand_percentage",
        translation_key="demand_percentage",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda data: data.device.demand_percentage,
        enabled=lambda data: data.device.demand_percentage is not None,
    ),
    MelcloudSensorEntityDescription(
        key="rssi",
        entity_registry_enabled_default=False,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.device.wifi_signal,
        enabled=lambda data: True,
    ),
    MelcloudSensorEntityDescription(
        key="energy_produced",
        translation_key="energy_produced",
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        value_fn=lambda data: data.device.get_device_prop("CurrentEnergyProduced"),
        enabled=lambda data: True,
    ),
    MelcloudSensorEntityDescription(
        key="daily_heating_energy_consumed",
        translation_key="daily_heating_energy_consumed",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=1,
        value_fn=lambda data: data.device.daily_heating_energy_consumed,
        enabled=lambda data: data.device.daily_heating_energy_consumed is not None,
    ),
    MelcloudSensorEntityDescription(
        key="daily_heating_energy_produced",
        translation_key="daily_heating_energy_produced",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=1,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.device.daily_heating_energy_produced,
        enabled=lambda data: data.device.daily_heating_energy_produced is not None,
    ),
    MelcloudSensorEntityDescription(
        key="daily_cooling_energy_consumed",
        translation_key="daily_cooling_energy_consumed",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=1,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.device.daily_cooling_energy_consumed,
        enabled=lambda data: data.device.daily_cooling_energy_consumed is not None,
    ),
    MelcloudSensorEntityDescription(
        key="daily_cooling_energy_produced",
        translation_key="daily_cooling_energy_produced",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=1,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.device.daily_cooling_energy_produced,
        enabled=lambda data: data.device.daily_cooling_energy_produced is not None,
    ),
    MelcloudSensorEntityDescription(
        key="daily_hot_water_energy_consumed",
        translation_key="daily_hot_water_energy_consumed",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=1,
        value_fn=lambda data: data.device.daily_hot_water_energy_consumed,
        enabled=lambda data: data.device.daily_hot_water_energy_consumed is not None,
    ),
    MelcloudSensorEntityDescription(
        key="daily_hot_water_energy_produced",
        translation_key="daily_hot_water_energy_produced",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=1,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.device.daily_hot_water_energy_produced,
        enabled=lambda data: data.device.daily_hot_water_energy_produced is not None,
    ),
)
ATW_ZONE_SENSORS: tuple[MelcloudSensorEntityDescription, ...] = (
    MelcloudSensorEntityDescription(
        key="room_temperature",
        translation_key="room_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda zone: zone.room_temperature,
        enabled=lambda data: True,
    ),
    MelcloudSensorEntityDescription(
        key="flow_temperature",
        translation_key="flow_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda zone: zone.zone_flow_temperature,
        enabled=lambda data: True,
    ),
    MelcloudSensorEntityDescription(
        key="return_temperature",
        translation_key="return_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda zone: zone.zone_return_temperature,
        enabled=lambda data: True,
    ),
)


async def async_setup_entry(
    _hass: HomeAssistant,
    entry: MelCloudConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up MELCloud device sensors based on config_entry."""
    coordinators = entry.runtime_data

    entities: list[MelDeviceSensor] = [
        MelDeviceSensor(coordinator, description)
        for description in ATA_SENSORS
        for coordinator in coordinators.get(DEVICE_TYPE_ATA, [])
        if description.enabled(coordinator)
    ] + [
        MelDeviceSensor(coordinator, description)
        for description in ATW_SENSORS
        for coordinator in coordinators.get(DEVICE_TYPE_ATW, [])
        if description.enabled(coordinator)
    ]
    entities.extend(
        [
            AtwZoneSensor(coordinator, zone, description)
            for coordinator in coordinators.get(DEVICE_TYPE_ATW, [])
            for zone in coordinator.device.zones
            for description in ATW_ZONE_SENSORS
            if description.enabled(zone)
        ]
    )
    async_add_entities(entities)


class MelDeviceSensor(MelCloudEntity, SensorEntity):
    """Representation of a Sensor."""

    entity_description: MelcloudSensorEntityDescription

    def __init__(
        self,
        coordinator: MelCloudDeviceUpdateCoordinator,
        description: MelcloudSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description

        self._attr_unique_id = (
            f"{coordinator.device.serial}-{coordinator.device.mac}-{description.key}"
        )
        self._attr_device_info = coordinator.device_info

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator)


class AtwZoneSensor(MelDeviceSensor):
    """Air-to-Water zone sensor."""

    def __init__(
        self,
        coordinator: MelCloudDeviceUpdateCoordinator,
        zone: Zone,
        description: MelcloudSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        if zone.zone_index != 1:
            description = dataclasses.replace(
                description,
                key=f"{description.key}-zone-{zone.zone_index}",
            )
        super().__init__(coordinator, description)

        self._attr_device_info = coordinator.zone_device_info(zone)
        self._zone = zone

    @property
    def native_value(self) -> float | None:
        """Return zone based state."""
        return self.entity_description.value_fn(self._zone)
