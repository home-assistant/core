"""Support for E3/DC sensors."""

from collections.abc import Callable
from dataclasses import dataclass
from enum import IntEnum
from typing import override

from e3dc_ess_modbus import E3dcPowerStation, EmergencyPowerStatus, PowerMeterType

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .coordinator import E3dcConfigEntry
from .entity import E3dcEntity

PARALLEL_UPDATES = 0


def _enum_options(enum_type: type[IntEnum]) -> list[str]:
    """The sensor options a device enum maps to."""
    return [member.name.lower() for member in enum_type]


@dataclass(frozen=True, kw_only=True)
class E3dcSensorDescription(SensorEntityDescription):
    """Describe an E3/DC sensor."""

    value_fn: Callable[[E3dcPowerStation], StateType | IntEnum]
    exists_fn: Callable[[E3dcPowerStation], bool] = lambda _: True


def _has_wallbox(device: E3dcPowerStation) -> bool:
    """Whether a wallbox is configured."""
    return bool(device.wallboxes.configured)


def _has_additional_feeder(device: E3dcPowerStation) -> bool:
    """Whether a power meter measures an additional feeder, e.g. a second PV inverter."""
    return any(
        meter.meter_type
        in (PowerMeterType.EXTERNAL_PRODUCTION, PowerMeterType.EXTERNAL_FARM)
        for meter in device.power_meter_readings.values()
    )


def _power(
    key: str,
    value_fn: Callable[[E3dcPowerStation], int | None],
    exists_fn: Callable[[E3dcPowerStation], bool] = lambda _: True,
) -> E3dcSensorDescription:
    """A power flow sensor, in watts."""
    return E3dcSensorDescription(
        key=key,
        translation_key=key,
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=value_fn,
        exists_fn=exists_fn,
    )


SENSORS: tuple[E3dcSensorDescription, ...] = (
    _power("pv_power", lambda device: device.power.pv_power),
    _power(
        "battery_power",
        # E3/DC reports charging as positive power
        # Negate it because Home Assistant expects discharging as positive
        lambda device: (
            None if (power := device.power.battery_power) is None else -power
        ),
    ),
    _power("house_power", lambda device: device.power.house_power),
    _power("grid_power", lambda device: device.power.grid_power),
    _power(
        "additional_power",
        lambda device: device.power.additional_power,
        _has_additional_feeder,
    ),
    _power("wallbox_power", lambda device: device.power.wallbox_power, _has_wallbox),
    _power(
        "wallbox_solar_power",
        lambda device: device.power.wallbox_solar_power,
        _has_wallbox,
    ),
    E3dcSensorDescription(
        key="battery_soc",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda device: device.power.battery_soc,
    ),
    E3dcSensorDescription(
        key="autarky",
        translation_key="autarky",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda device: device.power.autarky,
    ),
    E3dcSensorDescription(
        key="self_consumption",
        translation_key="self_consumption",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda device: device.power.self_consumption,
    ),
    E3dcSensorDescription(
        key="emergency_power_status",
        translation_key="emergency_power_status",
        device_class=SensorDeviceClass.ENUM,
        options=_enum_options(EmergencyPowerStatus),
        value_fn=lambda device: device.power.emergency_power_status,
        exists_fn=lambda device: (
            device.power.emergency_power_status
            is not EmergencyPowerStatus.NOT_SUPPORTED
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: E3dcConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the E3/DC sensor platform."""
    coordinator = entry.runtime_data
    async_add_entities(
        E3dcSensor(coordinator, description)
        for description in SENSORS
        if description.exists_fn(coordinator.device)
    )


class E3dcSensor(E3dcEntity, SensorEntity):
    """Defines an E3/DC sensor."""

    entity_description: E3dcSensorDescription

    @property
    @override
    def native_value(self) -> StateType:
        value = self.entity_description.value_fn(self.coordinator.device)
        if isinstance(value, IntEnum):
            return value.name.lower()
        return value
