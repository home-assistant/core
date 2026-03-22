"""Sensor platform for the EARN-E P1 Meter integration."""

from __future__ import annotations

from dataclasses import dataclass
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfVolume,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import EarnEP1ConfigEntry
from .coordinator import EarnEP1Coordinator
from .entity import EarnEP1Entity


@dataclass(frozen=True, kw_only=True)
class EarnEP1SensorEntityDescription(SensorEntityDescription):
    """Describes an EARN-E P1 sensor entity."""

    json_key: str | None = None


SENSOR_DESCRIPTIONS: tuple[EarnEP1SensorEntityDescription, ...] = (
    EarnEP1SensorEntityDescription(
        key="power_delivered",
        translation_key="power_delivered",
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    EarnEP1SensorEntityDescription(
        key="power_returned",
        translation_key="power_returned",
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    EarnEP1SensorEntityDescription(
        key="voltage_l1",
        translation_key="voltage_l1",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    EarnEP1SensorEntityDescription(
        key="current_l1",
        translation_key="current_l1",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    EarnEP1SensorEntityDescription(
        key="energy_delivered_tariff1",
        translation_key="energy_delivered_tariff1",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    EarnEP1SensorEntityDescription(
        key="energy_delivered_tariff2",
        translation_key="energy_delivered_tariff2",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    EarnEP1SensorEntityDescription(
        key="energy_returned_tariff1",
        translation_key="energy_returned_tariff1",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    EarnEP1SensorEntityDescription(
        key="energy_returned_tariff2",
        translation_key="energy_returned_tariff2",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    EarnEP1SensorEntityDescription(
        key="gas_delivered",
        translation_key="gas_delivered",
        native_unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        device_class=SensorDeviceClass.GAS,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    EarnEP1SensorEntityDescription(
        key="wifi_rssi",
        translation_key="wifi_rssi",
        json_key="wifiRSSI",
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EarnEP1ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up EARN-E P1 sensor entities."""
    coordinator = entry.runtime_data
    async_add_entities(
        EarnEP1Sensor(coordinator, description) for description in SENSOR_DESCRIPTIONS
    )


class EarnEP1Sensor(EarnEP1Entity, SensorEntity):
    """Representation of an EARN-E P1 sensor."""

    entity_description: EarnEP1SensorEntityDescription

    def __init__(
        self,
        coordinator: EarnEP1Coordinator,
        description: EarnEP1SensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._json_key = description.json_key or description.key
        self._attr_unique_id = f"{coordinator.identifier}_{description.key}"

    @property
    def available(self) -> bool:
        """Return True if the sensor value is available."""
        if not super().available:
            return False
        if not self.coordinator.data:
            return False
        return self._json_key in self.coordinator.data

    @property
    def native_value(self) -> StateType:
        """Return the sensor value."""
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get(self._json_key)
