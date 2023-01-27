"""Support for Lektrico charging station sensors."""
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
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_FRIENDLY_NAME,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import LektricoDeviceDataUpdateCoordinator
from .const import DOMAIN


@dataclass
class LektricoSensorEntityDescription(SensorEntityDescription):
    """A class that describes the Lektrico sensor entities."""

    value: Callable[[Any], float | str | int] | None = None


SENSORS: tuple[LektricoSensorEntityDescription, ...] = (
    LektricoSensorEntityDescription(
        key="charger_state",
        name="Charger state",
        value=lambda data: str(data.charger_state),
    ),
    LektricoSensorEntityDescription(
        key="charging_time",
        name="Charging time",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        value=lambda data: int(data.charging_time),
    ),
    LektricoSensorEntityDescription(
        key="current",
        name="Current",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        value=lambda data: float(data.current),
    ),
    LektricoSensorEntityDescription(
        key="instant_power",
        name="Instant power",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        value=lambda data: float(data.instant_power) / 1000,
    ),
    LektricoSensorEntityDescription(
        key="session_energy",
        name="Session energy",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        value=lambda data: float(data.session_energy) / 1000,
    ),
    LektricoSensorEntityDescription(
        key="temperature",
        name="Temperature",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value=lambda data: float(data.temperature),
    ),
    LektricoSensorEntityDescription(
        key="total_charged_energy",
        name="Total charged energy",
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        value=lambda data: int(data.total_charged_energy),
    ),
    LektricoSensorEntityDescription(
        key="voltage",
        name="Voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        value=lambda data: float(data.voltage),
    ),
    LektricoSensorEntityDescription(
        key="install_current",
        name="Install current",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        value=lambda data: int(data.install_current),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Lektrico charger based on a config entry."""
    coordinator: LektricoDeviceDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        LektricoSensor(
            description,
            coordinator,
            entry.data[CONF_FRIENDLY_NAME],
        )
        for description in SENSORS
    )


class LektricoSensor(CoordinatorEntity, SensorEntity):
    """The entity class for Lektrico charging stations sensors."""

    entity_description: LektricoSensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        description: LektricoSensorEntityDescription,
        coordinator: LektricoDeviceDataUpdateCoordinator,
        friendly_name: str,
    ) -> None:
        """Initialize Lektrico charger."""
        super().__init__(coordinator)
        self.entity_description = description

        self._attr_unique_id = f"{coordinator.serial_number}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.serial_number)},
            model=f"1P7K {coordinator.serial_number} rev.{coordinator.board_revision}",
            name=friendly_name,
            manufacturer="Lektrico",
            sw_version=coordinator.data.fw_version,
        )

    @property
    def native_value(self) -> float | str | int | None:
        """Return the state of the sensor."""
        if self.entity_description.value is None:
            return None
        return self.entity_description.value(self.coordinator.data)
