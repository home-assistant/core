"""Sensor platform for Duosida EV Charger."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DuosidaConfigEntry
from .const import CONF_DEVICE_ID, STATUS_CODES
from .coordinator import DuosidaDataUpdateCoordinator
from .entity import DuosidaEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True)
class DuosidaSensorEntityDescription(SensorEntityDescription):
    """Describes a Duosida sensor entity."""

    value_fn: Callable[[dict[str, Any]], Any] | None = None


SENSORS: tuple[DuosidaSensorEntityDescription, ...] = (
    DuosidaSensorEntityDescription(
        key="state",
        translation_key="status",
        icon="mdi:ev-station",
        value_fn=lambda data: STATUS_CODES.get(data.get("conn_status", 0), "Unknown"),
    ),
    DuosidaSensorEntityDescription(
        key="cp_voltage",
        translation_key="cp_voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:ev-plug-type2",
        value_fn=lambda data: data.get("cp_voltage"),
    ),
    DuosidaSensorEntityDescription(
        key="voltage",
        translation_key="voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.get("voltage"),
    ),
    DuosidaSensorEntityDescription(
        key="voltage_l2",
        translation_key="voltage_l2",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.get("voltage_l2"),
        entity_registry_enabled_default=False,
    ),
    DuosidaSensorEntityDescription(
        key="voltage_l3",
        translation_key="voltage_l3",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.get("voltage_l3"),
        entity_registry_enabled_default=False,
    ),
    DuosidaSensorEntityDescription(
        key="current",
        translation_key="current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.get("current"),
    ),
    DuosidaSensorEntityDescription(
        key="current_l2",
        translation_key="current_l2",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.get("current_l2"),
        entity_registry_enabled_default=False,
    ),
    DuosidaSensorEntityDescription(
        key="current_l3",
        translation_key="current_l3",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.get("current_l3"),
        entity_registry_enabled_default=False,
    ),
    DuosidaSensorEntityDescription(
        key="power",
        translation_key="power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.get("power"),
    ),
    DuosidaSensorEntityDescription(
        key="session_energy",
        translation_key="session_energy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: data.get("session_energy"),
    ),
    DuosidaSensorEntityDescription(
        key="session_time",
        translation_key="session_time",
        icon="mdi:timer",
        native_unit_of_measurement=UnitOfTime.HOURS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: (
            round(data.get("session_time", 0) / 60.0, 2)
            if data.get("session_time")
            else 0
        ),
    ),
    DuosidaSensorEntityDescription(
        key="total_energy",
        translation_key="total_energy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:lightning-bolt",
        value_fn=lambda data: data.get("total_energy"),
    ),
    DuosidaSensorEntityDescription(
        key="temperature",
        translation_key="temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.get("temperature_station"),
    ),
    DuosidaSensorEntityDescription(
        key="model",
        translation_key="model",
        icon="mdi:information",
        value_fn=lambda data: data.get("model"),
        entity_registry_enabled_default=False,
    ),
    DuosidaSensorEntityDescription(
        key="manufacturer",
        translation_key="manufacturer",
        icon="mdi:factory",
        value_fn=lambda data: data.get("manufacturer"),
        entity_registry_enabled_default=False,
    ),
    DuosidaSensorEntityDescription(
        key="firmware",
        translation_key="firmware",
        icon="mdi:chip",
        value_fn=lambda data: data.get("firmware"),
        entity_registry_enabled_default=False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DuosidaConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Duosida sensors."""
    coordinator = entry.runtime_data
    device_id = entry.data[CONF_DEVICE_ID]

    async_add_entities(
        DuosidaSensor(coordinator, device_id, description) for description in SENSORS
    )


class DuosidaSensor(DuosidaEntity, SensorEntity):
    """Representation of a Duosida sensor."""

    entity_description: DuosidaSensorEntityDescription

    def __init__(
        self,
        coordinator: DuosidaDataUpdateCoordinator,
        device_id: str,
        description: DuosidaSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, device_id)
        self.entity_description = description
        self._attr_unique_id = f"{device_id}_{description.key}"

    @property
    def native_value(self) -> Any:
        """Return the state of the sensor."""
        if not self.coordinator.data:
            return None

        if self.entity_description.value_fn is None:
            return None
        return self.entity_description.value_fn(self.coordinator.data)
