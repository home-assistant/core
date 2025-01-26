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
from homeassistant.const import (
    ATTR_SERIAL_NUMBER,
    CONF_TYPE,
    PERCENTAGE,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import IntegrationError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import LektricoConfigEntry, LektricoDeviceDataUpdateCoordinator
from .entity import LektricoEntity


@dataclass(frozen=True, kw_only=True)
class LektricoSensorEntityDescription(SensorEntityDescription):
    """A class that describes the Lektrico sensor entities."""

    value_fn: Callable[[dict[str, Any]], StateType]


LIMIT_REASON_OPTIONS = [
    "no_limit",
    "installation_current",
    "user_limit",
    "dynamic_limit",
    "schedule",
    "em_offline",
    "em",
    "ocpp",
    "overtemperature",
    "switching_phases",
    "1p_charging_disabled",
]


SENSORS_FOR_CHARGERS: tuple[LektricoSensorEntityDescription, ...] = (
    LektricoSensorEntityDescription(
        key="state",
        device_class=SensorDeviceClass.ENUM,
        options=[
            "available",
            "charging",
            "connected",
            "error",
            "locked",
            "need_auth",
            "paused",
            "paused_by_scheduler",
            "updating_firmware",
        ],
        translation_key="state",
        value_fn=lambda data: str(data["charger_state"]),
    ),
    LektricoSensorEntityDescription(
        key="charging_time",
        translation_key="charging_time",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        value_fn=lambda data: int(data["charging_time"]),
    ),
    LektricoSensorEntityDescription(
        key="power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_unit_of_measurement=UnitOfPower.KILO_WATT,
        value_fn=lambda data: float(data["instant_power"]),
    ),
    LektricoSensorEntityDescription(
        key="energy",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        value_fn=lambda data: float(data["session_energy"]) / 1000,
    ),
    LektricoSensorEntityDescription(
        key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda data: float(data["temperature"]),
    ),
    LektricoSensorEntityDescription(
        key="lifetime_energy",
        translation_key="lifetime_energy",
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        value_fn=lambda data: int(data["total_charged_energy"]),
    ),
    LektricoSensorEntityDescription(
        key="installation_current",
        translation_key="installation_current",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        value_fn=lambda data: int(data["install_current"]),
    ),
    LektricoSensorEntityDescription(
        key="limit_reason",
        translation_key="limit_reason",
        device_class=SensorDeviceClass.ENUM,
        options=LIMIT_REASON_OPTIONS,
        value_fn=lambda data: (
            str(data["current_limit_reason"])
            if str(data["current_limit_reason"]) in LIMIT_REASON_OPTIONS
            else None
        ),
    ),
)

SENSORS_FOR_LB_DEVICES: tuple[LektricoSensorEntityDescription, ...] = (
    LektricoSensorEntityDescription(
        key="breaker_current",
        translation_key="breaker_current",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        value_fn=lambda data: int(data["breaker_curent"]),
    ),
)

SENSORS_FOR_1_PHASE: tuple[LektricoSensorEntityDescription, ...] = (
    LektricoSensorEntityDescription(
        key="voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        value_fn=lambda data: float(data["voltage_l1"]),
    ),
    LektricoSensorEntityDescription(
        key="current",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        value_fn=lambda data: float(data["current_l1"]),
    ),
)

SENSORS_FOR_3_PHASE: tuple[LektricoSensorEntityDescription, ...] = (
    LektricoSensorEntityDescription(
        key="voltage_l1",
        translation_key="voltage_l1",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        value_fn=lambda data: float(data["voltage_l1"]),
    ),
    LektricoSensorEntityDescription(
        key="voltage_l2",
        translation_key="voltage_l2",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        value_fn=lambda data: float(data["voltage_l2"]),
    ),
    LektricoSensorEntityDescription(
        key="voltage_l3",
        translation_key="voltage_l3",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        value_fn=lambda data: float(data["voltage_l3"]),
    ),
    LektricoSensorEntityDescription(
        key="current_l1",
        translation_key="current_l1",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        value_fn=lambda data: float(data["current_l1"]),
    ),
    LektricoSensorEntityDescription(
        key="current_l2",
        translation_key="current_l2",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        value_fn=lambda data: float(data["current_l2"]),
    ),
    LektricoSensorEntityDescription(
        key="current_l3",
        translation_key="current_l3",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        value_fn=lambda data: float(data["current_l3"]),
    ),
)


SENSORS_FOR_LB_1_PHASE: tuple[LektricoSensorEntityDescription, ...] = (
    LektricoSensorEntityDescription(
        key="power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_unit_of_measurement=UnitOfPower.KILO_WATT,
        value_fn=lambda data: float(data["power_l1"]),
    ),
    LektricoSensorEntityDescription(
        key="pf",
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda data: float(data["power_factor_l1"]) * 100,
    ),
)


SENSORS_FOR_LB_3_PHASE: tuple[LektricoSensorEntityDescription, ...] = (
    LektricoSensorEntityDescription(
        key="power_l1",
        translation_key="power_l1",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_unit_of_measurement=UnitOfPower.KILO_WATT,
        value_fn=lambda data: float(data["power_l1"]),
    ),
    LektricoSensorEntityDescription(
        key="power_l2",
        translation_key="power_l2",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_unit_of_measurement=UnitOfPower.KILO_WATT,
        value_fn=lambda data: float(data["power_l2"]),
    ),
    LektricoSensorEntityDescription(
        key="power_l3",
        translation_key="power_l3",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_unit_of_measurement=UnitOfPower.KILO_WATT,
        value_fn=lambda data: float(data["power_l3"]),
    ),
    LektricoSensorEntityDescription(
        key="pf_l1",
        translation_key="pf_l1",
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda data: float(data["power_factor_l1"]) * 100,
    ),
    LektricoSensorEntityDescription(
        key="pf_l2",
        translation_key="pf_l2",
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda data: float(data["power_factor_l2"]) * 100,
    ),
    LektricoSensorEntityDescription(
        key="pf_l3",
        translation_key="pf_l3",
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda data: float(data["power_factor_l3"]) * 100,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LektricoConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Lektrico charger based on a config entry."""
    coordinator = entry.runtime_data

    sensors_to_be_used: tuple[LektricoSensorEntityDescription, ...]
    if coordinator.device_type == Device.TYPE_1P7K:
        sensors_to_be_used = SENSORS_FOR_CHARGERS + SENSORS_FOR_1_PHASE
    elif coordinator.device_type == Device.TYPE_3P22K:
        sensors_to_be_used = SENSORS_FOR_CHARGERS + SENSORS_FOR_3_PHASE
    elif coordinator.device_type == Device.TYPE_EM:
        sensors_to_be_used = (
            SENSORS_FOR_LB_DEVICES + SENSORS_FOR_1_PHASE + SENSORS_FOR_LB_1_PHASE
        )
    elif coordinator.device_type == Device.TYPE_3EM:
        sensors_to_be_used = (
            SENSORS_FOR_LB_DEVICES + SENSORS_FOR_3_PHASE + SENSORS_FOR_LB_3_PHASE
        )
    else:
        raise IntegrationError

    async_add_entities(
        LektricoSensor(
            description,
            coordinator,
            f"{entry.data[CONF_TYPE]}_{entry.data[ATTR_SERIAL_NUMBER]}",
        )
        for description in sensors_to_be_used
    )


class LektricoSensor(LektricoEntity, SensorEntity):
    """The entity class for Lektrico charging stations sensors."""

    entity_description: LektricoSensorEntityDescription

    def __init__(
        self,
        description: LektricoSensorEntityDescription,
        coordinator: LektricoDeviceDataUpdateCoordinator,
        device_name: str,
    ) -> None:
        """Initialize Lektrico charger."""
        super().__init__(coordinator, device_name)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.serial_number}_{description.key}"

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)
