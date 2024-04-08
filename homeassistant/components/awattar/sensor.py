"""Support for aWATTar sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CURRENCY_EURO, UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .coordinator import AwattarData, AwattarDataUpdateCoordinator


@dataclass(frozen=True, kw_only=True)
class AwattarSensorEntityDescription(SensorEntityDescription):
    """Describes a aWATTar sensor entity."""

    value_fn: Callable[[AwattarData], float | datetime | None]


SENSORS: tuple[AwattarSensorEntityDescription, ...] = (
    AwattarSensorEntityDescription(
        key="current_hour_price",
        translation_key="current_hour_price",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=4,
        native_unit_of_measurement=f"{CURRENCY_EURO}/{UnitOfEnergy.KILO_WATT_HOUR}",
        value_fn=lambda data: data.awattar.for_timestamp(dt_util.now()).price_per_kWh,
    ),
    AwattarSensorEntityDescription(
        key="next_hour_price",
        translation_key="next_hour_price",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=4,
        native_unit_of_measurement=f"{CURRENCY_EURO}/{UnitOfEnergy.KILO_WATT_HOUR}",
        value_fn=lambda data: (
            data.awattar.for_timestamp(dt_util.now() + timedelta(0, 3600)).price_per_kWh
        ),
    ),
    AwattarSensorEntityDescription(
        key="average_price",
        translation_key="average_price",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=4,
        native_unit_of_measurement=f"{CURRENCY_EURO}/{UnitOfEnergy.KILO_WATT_HOUR}",
        value_fn=lambda data: data.awattar.mean().price_per_kWh,
    ),
    AwattarSensorEntityDescription(
        key="max_price",
        translation_key="max_price",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=4,
        native_unit_of_measurement=f"{CURRENCY_EURO}/{UnitOfEnergy.KILO_WATT_HOUR}",
        value_fn=lambda data: data.awattar.max().price_per_kWh,
    ),
    AwattarSensorEntityDescription(
        key="min_price",
        translation_key="min_price",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=4,
        native_unit_of_measurement=f"{CURRENCY_EURO}/{UnitOfEnergy.KILO_WATT_HOUR}",
        value_fn=lambda data: data.awattar.min().price_per_kWh,
    ),
    AwattarSensorEntityDescription(
        key="slot_2_hrs_start",
        translation_key="slot_2_hrs_start",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda data: data.awattar.best_slot(2).start_datetime,
    ),
    AwattarSensorEntityDescription(
        key="slot_3_hrs_start",
        translation_key="slot_3_hrs_start",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda data: data.awattar.best_slot(3).start_datetime,
    ),
    AwattarSensorEntityDescription(
        key="slot_4_hrs_start",
        translation_key="slot_4_hrs_start",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda data: data.awattar.best_slot(4).start_datetime,
    ),
    AwattarSensorEntityDescription(
        key="slot_5_hrs_start",
        translation_key="slot_5_hrs_start",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda data: data.awattar.best_slot(5).start_datetime,
    ),
    AwattarSensorEntityDescription(
        key="slot_6_hrs_start",
        translation_key="slot_6_hrs_start",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda data: data.awattar.best_slot(6).start_datetime,
    ),
    AwattarSensorEntityDescription(
        key="slot_2_hrs_price",
        translation_key="slot_2_hrs_price",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=f"{CURRENCY_EURO}/{UnitOfEnergy.KILO_WATT_HOUR}",
        value_fn=lambda data: data.awattar.best_slot(2).price_per_kWh,
    ),
    AwattarSensorEntityDescription(
        key="slot_3_hrs_price",
        translation_key="slot_3_hrs_price",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=4,
        native_unit_of_measurement=f"{CURRENCY_EURO}/{UnitOfEnergy.KILO_WATT_HOUR}",
        value_fn=lambda data: data.awattar.best_slot(3).price_per_kWh,
    ),
    AwattarSensorEntityDescription(
        key="slot_4_hrs_price",
        translation_key="slot_4_hrs_price",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=4,
        native_unit_of_measurement=f"{CURRENCY_EURO}/{UnitOfEnergy.KILO_WATT_HOUR}",
        value_fn=lambda data: data.awattar.best_slot(4).price_per_kWh,
    ),
    AwattarSensorEntityDescription(
        key="slot_5_hrs_price",
        translation_key="slot_5_hrs_price",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=4,
        native_unit_of_measurement=f"{CURRENCY_EURO}/{UnitOfEnergy.KILO_WATT_HOUR}",
        value_fn=lambda data: data.awattar.best_slot(5).price_per_kWh,
    ),
    AwattarSensorEntityDescription(
        key="slot_6_hrs_price",
        translation_key="slot_6_hrs_price",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=4,
        native_unit_of_measurement=f"{CURRENCY_EURO}/{UnitOfEnergy.KILO_WATT_HOUR}",
        value_fn=lambda data: data.awattar.best_slot(6).price_per_kWh,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up aWATTar Sensors based on a config entry."""
    coordinator: AwattarDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        AwattarSensorEntity(
            coordinator=coordinator,
            description=description,
        )
        for description in SENSORS
    )


class AwattarSensorEntity(
    CoordinatorEntity[AwattarDataUpdateCoordinator], SensorEntity
):
    """Defines a aWATTar sensor."""

    _attr_has_entity_name = True
    entity_description: AwattarSensorEntityDescription

    def __init__(
        self,
        coordinator: AwattarDataUpdateCoordinator,
        description: AwattarSensorEntityDescription,
    ) -> None:
        """Initialize aWATTar sensor."""
        super().__init__(coordinator=coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={
                (
                    DOMAIN,
                    f"{coordinator.config_entry.entry_id}",
                )
            },
            manufacturer="aWATTar",
            name="Energy market price",
        )

    @property
    def native_value(self) -> float | datetime | None:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)
