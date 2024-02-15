"""Platform for sensor integration."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from technove import Station as TechnoVEStation, Status

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import DOMAIN
from .coordinator import TechnoVEDataUpdateCoordinator
from .entity import TechnoVEEntity

STATUS_TYPE = [s.value for s in Status if s != Status.UNKNOWN]


@dataclass(frozen=True, kw_only=True)
class TechnoVESensorEntityDescription(SensorEntityDescription):
    """Describes TechnoVE sensor entity."""

    value_fn: Callable[[TechnoVEStation], StateType]


SENSORS: tuple[TechnoVESensorEntityDescription, ...] = (
    TechnoVESensorEntityDescription(
        key="voltage_in",
        translation_key="voltage_in",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda station: station.info.voltage_in,
    ),
    TechnoVESensorEntityDescription(
        key="voltage_out",
        translation_key="voltage_out",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda station: station.info.voltage_out,
    ),
    TechnoVESensorEntityDescription(
        key="max_station_current",
        translation_key="max_station_current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda station: station.info.max_station_current,
    ),
    TechnoVESensorEntityDescription(
        key="current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda station: station.info.current,
    ),
    TechnoVESensorEntityDescription(
        key="energy_total",
        translation_key="energy_total",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda station: station.info.energy_total,
    ),
    TechnoVESensorEntityDescription(
        key="energy_session",
        translation_key="energy_session",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda station: station.info.energy_session,
    ),
    TechnoVESensorEntityDescription(
        key="rssi",
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda station: station.info.rssi,
    ),
    TechnoVESensorEntityDescription(
        key="ssid",
        translation_key="ssid",
        icon="mdi:wifi",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda station: station.info.network_ssid,
    ),
    TechnoVESensorEntityDescription(
        key="status",
        translation_key="status",
        device_class=SensorDeviceClass.ENUM,
        options=STATUS_TYPE,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda station: station.info.status.value,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    coordinator: TechnoVEDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        TechnoVESensorEntity(coordinator, description) for description in SENSORS
    )


class TechnoVESensorEntity(TechnoVEEntity, SensorEntity):
    """Defines a TechnoVE sensor entity."""

    entity_description: TechnoVESensorEntityDescription

    def __init__(
        self,
        coordinator: TechnoVEDataUpdateCoordinator,
        description: TechnoVESensorEntityDescription,
    ) -> None:
        """Initialize a TechnoVE sensor entity."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)
