"""Support for EnergyZero sensors."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    DOMAIN as SENSOR_DOMAIN,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CURRENCY_EURO,
    ENERGY_KILO_WATT_HOUR,
    PERCENTAGE,
    VOLUME_CUBIC_METERS,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTRIBUTION,
    CONF_GAS,
    DOMAIN,
    SERVICE_ENERGY_TODAY,
    SERVICE_ENERGY_TOMORROW,
    SERVICE_GAS_TODAY,
)
from .coordinator import EnergyZeroData, EnergyZeroDataUpdateCoordinator


@dataclass
class EnergyZeroSensorEntityDescriptionMixin:
    """Mixin for required keys."""

    value_fn: Callable[[EnergyZeroData], float | datetime | None]


@dataclass
class EnergyZeroSensorEntityDescription(
    SensorEntityDescription, EnergyZeroSensorEntityDescriptionMixin
):
    """Describes a Pure Energie sensor entity."""


SENSORS_GAS: tuple[EnergyZeroSensorEntityDescription, ...] = (
    EnergyZeroSensorEntityDescription(
        key="current_hour_price",
        name="Current gas market price",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=f"{CURRENCY_EURO}/{VOLUME_CUBIC_METERS}",
        value_fn=lambda data: data[SERVICE_GAS_TODAY].current_hourprice
        if data[SERVICE_GAS_TODAY]
        else None,
    ),
    EnergyZeroSensorEntityDescription(
        key="next_hour_price",
        name="Next hour gas market price",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement=f"{CURRENCY_EURO}/{VOLUME_CUBIC_METERS}",
        value_fn=lambda data: data[SERVICE_GAS_TODAY].next_hourprice
        if data[SERVICE_GAS_TODAY]
        else None,
    ),
)

SENSORS_ENERGY: tuple[EnergyZeroSensorEntityDescription, ...] = (
    EnergyZeroSensorEntityDescription(
        key="current_hour_price",
        name="Current electricity market price",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=f"{CURRENCY_EURO}/{ENERGY_KILO_WATT_HOUR}",
        value_fn=lambda data: data[SERVICE_ENERGY_TODAY].current_hourprice,
    ),
    EnergyZeroSensorEntityDescription(
        key="next_hour_price",
        name="Next hour electricity market price",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement=f"{CURRENCY_EURO}/{ENERGY_KILO_WATT_HOUR}",
        value_fn=lambda data: data[SERVICE_ENERGY_TODAY].next_hourprice,
    ),
    EnergyZeroSensorEntityDescription(
        key="average_price",
        name="Average electricity market price - Today",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement=f"{CURRENCY_EURO}/{ENERGY_KILO_WATT_HOUR}",
        value_fn=lambda data: data[SERVICE_ENERGY_TODAY].average_price,
    ),
    EnergyZeroSensorEntityDescription(
        key="max_price",
        name="Highest Price - Today",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement=f"{CURRENCY_EURO}/{ENERGY_KILO_WATT_HOUR}",
        value_fn=lambda data: data[SERVICE_ENERGY_TODAY].max_price,
    ),
    EnergyZeroSensorEntityDescription(
        key="min_price",
        name="Lowest Price - Today",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement=f"{CURRENCY_EURO}/{ENERGY_KILO_WATT_HOUR}",
        value_fn=lambda data: data[SERVICE_ENERGY_TODAY].min_price,
    ),
    EnergyZeroSensorEntityDescription(
        key="highest_price_time",
        name="Time of highest price - Today",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda data: data[SERVICE_ENERGY_TODAY].highest_price_time,
    ),
    EnergyZeroSensorEntityDescription(
        key="lowest_price_time",
        name="Time of lowest price - Today",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda data: data[SERVICE_ENERGY_TODAY].lowest_price_time,
    ),
    EnergyZeroSensorEntityDescription(
        key="percentage_of_max",
        name="Current percentage of highest electricity price - Today",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:percent",
        value_fn=lambda data: data[SERVICE_ENERGY_TODAY].percentage_of_max_price,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up EnergyZero Sensors based on a config entry."""
    coordinator: EnergyZeroDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[EnergyZeroSensorEntity] = []
    entities.extend(
        EnergyZeroSensorEntity(
            coordinator=coordinator,
            description=description,
            name="Energy Market Price",
            service="today_energy",
        )
        for description in SENSORS_ENERGY
    )
    if entry.data[CONF_GAS]:
        entities.extend(
            EnergyZeroSensorEntity(
                coordinator=coordinator,
                description=description,
                name="Gas Market Price",
                service="today_gas",
            )
            for description in SENSORS_GAS
        )
    async_add_entities(entities)


class EnergyZeroSensorEntity(
    CoordinatorEntity[EnergyZeroDataUpdateCoordinator], SensorEntity
):
    """Defines a EnergyZero sensor."""

    _attr_attribution = ATTRIBUTION
    entity_description: EnergyZeroSensorEntityDescription

    def __init__(
        self,
        *,
        coordinator: EnergyZeroDataUpdateCoordinator,
        description: EnergyZeroSensorEntityDescription,
        name: str,
        service: str,
    ) -> None:
        """Initialize EnergyZero sensor."""
        super().__init__(coordinator=coordinator)
        self.entity_id = f"{SENSOR_DOMAIN}.energyzero_{service}_{description.key}"
        self.entity_description = description
        self._attr_unique_id = (
            f"{coordinator.config_entry.entry_id}_{service}_{description.key}"
        )

        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, f"{coordinator.config_entry.entry_id}_{service}")},
            manufacturer="EnergyZero",
            name=name,
        )

    @property
    def native_value(self) -> float | datetime | None:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes."""
        if self.entity_description.key == "average_price":
            return {
                "today": self.coordinator.data[SERVICE_ENERGY_TODAY].timestamp_prices,
                "tomorrow": self.coordinator.data[
                    SERVICE_ENERGY_TOMORROW
                ].timestamp_prices
                if self.coordinator.data[SERVICE_ENERGY_TOMORROW]
                else None,
            }
        return None
