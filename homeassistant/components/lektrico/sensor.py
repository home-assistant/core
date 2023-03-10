"""Support for Lektrico charging station sensors."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from lektricowifi import Device

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_FRIENDLY_NAME,
    PERCENTAGE,
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


SENSORS_FOR_CHARGERS: tuple[LektricoSensorEntityDescription, ...] = (
    LektricoSensorEntityDescription(
        key="state",
        name="State",
        value=lambda data: str(data.charger_state),
    ),
    LektricoSensorEntityDescription(
        key="charging_time",
        name="Charging time",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        value=lambda data: int(data.charging_time),
    ),
    LektricoSensorEntityDescription(
        key="power",
        name="Power",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        value=lambda data: float(data.instant_power) / 1000,
    ),
    LektricoSensorEntityDescription(
        key="energy",
        name="Energy",
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
        key="lifetime_energy",
        name="Lifetime energy",
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        value=lambda data: int(data.total_charged_energy),
    ),
    LektricoSensorEntityDescription(
        key="installation_current",
        name="Installation current",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        value=lambda data: int(data.install_current),
    ),
    LektricoSensorEntityDescription(
        key="limit_reason",
        name="Limit reason",
        value=lambda data: str(data.current_limit_reason),
    ),
)

SENSORS_FOR_LB_DEVICES: tuple[LektricoSensorEntityDescription, ...] = (
    LektricoSensorEntityDescription(
        key="breaker_current",
        name="Breaker current",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        value=lambda data: int(data.breaker_curent),
    ),
)

SENSORS_FOR_1_PHASE: tuple[LektricoSensorEntityDescription, ...] = (
    LektricoSensorEntityDescription(
        key="voltage",
        name="Voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        value=lambda data: float(data.voltage_l1),
    ),
    LektricoSensorEntityDescription(
        key="current",
        name="Current",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        value=lambda data: float(data.current_l1),
    ),
)

SENSORS_FOR_3_PHASE: tuple[LektricoSensorEntityDescription, ...] = (
    LektricoSensorEntityDescription(
        key="voltage_l1",
        name="Voltage L1",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        value=lambda data: float(data.voltage_l1),
    ),
    LektricoSensorEntityDescription(
        key="voltage_l2",
        name="Voltage L2",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        value=lambda data: float(data.voltage_l2),
    ),
    LektricoSensorEntityDescription(
        key="voltage_l3",
        name="Voltage L3",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        value=lambda data: float(data.voltage_l3),
    ),
    LektricoSensorEntityDescription(
        key="current_l1",
        name="Current L1",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        value=lambda data: float(data.current_l1),
    ),
    LektricoSensorEntityDescription(
        key="current_l2",
        name="Current L2",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        value=lambda data: float(data.current_l2),
    ),
    LektricoSensorEntityDescription(
        key="current_l3",
        name="Current L3",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        value=lambda data: float(data.current_l3),
    ),
)


SENSORS_FOR_LB_1_PHASE: tuple[LektricoSensorEntityDescription, ...] = (
    LektricoSensorEntityDescription(
        key="power",
        name="Power",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        value=lambda data: float(data.power_l1) / 1000,
    ),
    LektricoSensorEntityDescription(
        key="pf",
        name="PF",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER_FACTOR,
        native_unit_of_measurement=PERCENTAGE,
        value=lambda data: float(data.power_factor_l1) * 100,
    ),
)


SENSORS_FOR_LB_3_PHASE: tuple[LektricoSensorEntityDescription, ...] = (
    LektricoSensorEntityDescription(
        key="power_l1",
        name="Power L1",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        value=lambda data: float(data.power_l1) / 1000,
    ),
    LektricoSensorEntityDescription(
        key="power_l2",
        name="Power L2",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        value=lambda data: float(data.power_l2) / 1000,
    ),
    LektricoSensorEntityDescription(
        key="power_l3",
        name="Power L3",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        value=lambda data: float(data.power_l3) / 1000,
    ),
    LektricoSensorEntityDescription(
        key="pf_l1",
        name="PF L1",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER_FACTOR,
        native_unit_of_measurement=PERCENTAGE,
        value=lambda data: float(data.power_factor_l1) * 100,
    ),
    LektricoSensorEntityDescription(
        key="pf_l2",
        name="PF L2",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER_FACTOR,
        native_unit_of_measurement=PERCENTAGE,
        value=lambda data: float(data.power_factor_l2) * 100,
    ),
    LektricoSensorEntityDescription(
        key="pf_l3",
        name="PF L3",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER_FACTOR,
        native_unit_of_measurement=PERCENTAGE,
        value=lambda data: float(data.power_factor_l3) * 100,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Lektrico charger based on a config entry."""
    coordinator: LektricoDeviceDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    _sensors_to_be_used: tuple[LektricoSensorEntityDescription, ...]
    if coordinator.device_type == Device.TYPE_1P7K:
        _sensors_to_be_used = SENSORS_FOR_CHARGERS + SENSORS_FOR_1_PHASE
    elif coordinator.device_type == Device.TYPE_3P22K:
        _sensors_to_be_used = SENSORS_FOR_CHARGERS + SENSORS_FOR_3_PHASE
    elif coordinator.device_type == Device.TYPE_EM:
        _sensors_to_be_used = (
            SENSORS_FOR_LB_DEVICES + SENSORS_FOR_1_PHASE + SENSORS_FOR_LB_1_PHASE
        )
    elif coordinator.device_type == Device.TYPE_3EM:
        _sensors_to_be_used = (
            SENSORS_FOR_LB_DEVICES + SENSORS_FOR_3_PHASE + SENSORS_FOR_LB_3_PHASE
        )
    else:
        return

    async_add_entities(
        LektricoSensor(
            description,
            coordinator,
            entry.data[CONF_FRIENDLY_NAME],
        )
        for description in _sensors_to_be_used
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
            identifiers={(DOMAIN, str(coordinator.serial_number))},
            model=f"{coordinator.device_type.upper()} {coordinator.serial_number} rev.{coordinator.board_revision}",
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
