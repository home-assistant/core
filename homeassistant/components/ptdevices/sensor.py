"""Sensors for PTDevices device."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
import logging
from typing import cast

from aioptdevices.interface import PTDevicesStatusStates

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
    UnitOfElectricPotential,
    UnitOfLength,
    UnitOfTemperature,
    UnitOfVolume,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import PTDevicesConfigEntry, PTDevicesCoordinator

_LOGGER = logging.getLogger(__name__)


class PTDevicesSensors(StrEnum):
    """Store keys for PTDevices sensors."""

    LEVEL_PERCENT = "percent_level"
    LEVEL_VOLUME = "volume_level"
    LEVEL_DEPTH = "inch_level"
    PROBE_TEMPERATURE = "probe_temperature"
    DEVICE_STATUS = "status"
    DEVICE_LAST_REPORT = "reported"
    DEVICE_WIFI_STRENGTH = "wifi_signal"
    DEVICE_BATTERY_VOLTAGE = "battery_voltage"
    DEVICE_BATTERY_STATUS = "battery_status"
    TX_LAST_REPORT = "tx_reported"
    TX_SIGNAL_STRENGTH = "tx_signal"


@dataclass(kw_only=True, frozen=True)
class PTDevicesSensorEntityDescription(SensorEntityDescription):
    """Description for PTDevices sensor entities."""

    value_fn: Callable[[dict[str, str | int | float | None]], str | int | float | None]


SENSOR_DESCRIPTIONS: tuple[PTDevicesSensorEntityDescription, ...] = (
    PTDevicesSensorEntityDescription(
        key=PTDevicesSensors.LEVEL_PERCENT,
        translation_key=PTDevicesSensors.LEVEL_PERCENT,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: cast(float, data.get(PTDevicesSensors.LEVEL_PERCENT)),
    ),
    PTDevicesSensorEntityDescription(
        key=PTDevicesSensors.LEVEL_VOLUME,
        translation_key=PTDevicesSensors.LEVEL_VOLUME,
        native_unit_of_measurement=UnitOfVolume.LITERS,
        device_class=SensorDeviceClass.WATER,
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda data: cast(float, data.get(PTDevicesSensors.LEVEL_VOLUME)),
    ),
    PTDevicesSensorEntityDescription(
        key=PTDevicesSensors.LEVEL_DEPTH,
        translation_key=PTDevicesSensors.LEVEL_DEPTH,
        native_unit_of_measurement=UnitOfLength.METERS,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: cast(float, data.get(PTDevicesSensors.LEVEL_DEPTH)),
        suggested_display_precision=3,
    ),
    PTDevicesSensorEntityDescription(
        key=PTDevicesSensors.PROBE_TEMPERATURE,
        translation_key=PTDevicesSensors.PROBE_TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: cast(float, data.get(PTDevicesSensors.PROBE_TEMPERATURE)),
    ),
    PTDevicesSensorEntityDescription(
        key=PTDevicesSensors.DEVICE_STATUS,
        translation_key=PTDevicesSensors.DEVICE_STATUS,
        device_class=SensorDeviceClass.ENUM,
        options=[member.value for member in PTDevicesStatusStates],
        value_fn=lambda data: cast(str, data.get(PTDevicesSensors.DEVICE_STATUS)),
    ),
    PTDevicesSensorEntityDescription(
        key=PTDevicesSensors.DEVICE_WIFI_STRENGTH,
        translation_key=PTDevicesSensors.DEVICE_WIFI_STRENGTH,
        native_unit_of_measurement=PERCENTAGE,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: cast(
            int, data.get(PTDevicesSensors.DEVICE_WIFI_STRENGTH)
        ),
    ),
    PTDevicesSensorEntityDescription(
        key=PTDevicesSensors.TX_SIGNAL_STRENGTH,
        translation_key=PTDevicesSensors.TX_SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: cast(
            float, data.get(PTDevicesSensors.TX_SIGNAL_STRENGTH)
        ),
    ),
    PTDevicesSensorEntityDescription(
        key=PTDevicesSensors.DEVICE_BATTERY_STATUS,
        translation_key=PTDevicesSensors.DEVICE_BATTERY_STATUS,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: cast(
            str, data.get(PTDevicesSensors.DEVICE_BATTERY_STATUS)
        ),
    ),
    PTDevicesSensorEntityDescription(
        key=PTDevicesSensors.DEVICE_BATTERY_VOLTAGE,
        translation_key=PTDevicesSensors.DEVICE_BATTERY_VOLTAGE,
        device_class=SensorDeviceClass.VOLTAGE,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: cast(
            float, data.get(PTDevicesSensors.DEVICE_BATTERY_VOLTAGE)
        ),
        suggested_display_precision=2,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: PTDevicesConfigEntry,
    async_add_entity: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up PTDevices sensors from config entries."""
    coordinator = config_entry.runtime_data

    def _check_device() -> None:
        current_devices = set(coordinator.data.keys())
        new_devices = current_devices - coordinator.previous_devices
        if new_devices:
            for device_id in new_devices:
                device = coordinator.data[device_id]
                async_add_entity(
                    PTDevicesSensorEntity(config_entry.runtime_data, sensor, device_id)
                    for sensor in SENSOR_DESCRIPTIONS
                    if sensor.key in device
                )
        coordinator.previous_devices = current_devices

    _check_device()
    config_entry.async_on_unload(coordinator.async_add_listener(_check_device))


# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0


class PTDevicesSensorEntity(CoordinatorEntity[PTDevicesCoordinator], SensorEntity):
    """Sensor entity for PTDevices Integration."""

    _attr_has_entity_name = True
    entity_description: PTDevicesSensorEntityDescription

    def __init__(
        self,
        coordinator: PTDevicesCoordinator,
        description: PTDevicesSensorEntityDescription,
        device_id: str,
    ) -> None:
        """Initialize sensor."""
        super().__init__(coordinator=coordinator)

        self.entity_description = description
        self._device_id = device_id
        self._attr_unique_id = f"{device_id}_{description.key}"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            configuration_url=f"https://www.ptdevices.com/device/level/{self._device_id}",
            manufacturer="ParemTech inc.",
            model=self.coordinator.data[self._device_id].get(
                "device_type",
                None,
            ),
            sw_version=self.coordinator.data[self._device_id].get(
                "version",
                None,
            ),
            name=self.coordinator.data[self._device_id].get(
                "title",
                None,
            ),
        )

    @property
    def native_value(self) -> float | int | str | None:
        """Return the state of the senor."""
        # return self.coordinator.data[self._device_id].get(self.entity_description.key)
        return self.entity_description.value_fn(self.coordinator.data[self._device_id])

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return (
            super().available
            and self.entity_description.key
            in self.coordinator.data.get(self._device_id, {})
        )
