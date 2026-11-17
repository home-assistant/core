"""Support for E3/DC binary sensors."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from e3dc_ess_modbus import E3dcPowerStation, EmsStatus

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import E3dcConfigEntry
from .entity import E3dcEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class E3dcBinarySensorDescription(BinarySensorEntityDescription):
    """Describe an E3/DC binary sensor."""

    value_fn: Callable[[E3dcPowerStation], bool | None]


def _ems_flag(
    key: str, flag: EmsStatus, *, enabled: bool = True
) -> E3dcBinarySensorDescription:
    """A binary sensor for one bit of the EMS status register."""

    def _value(device: E3dcPowerStation) -> bool | None:
        status = device.power.ems_status
        return None if status is None else flag in status

    return E3dcBinarySensorDescription(
        key=key,
        translation_key=key,
        entity_registry_enabled_default=enabled,
        value_fn=_value,
    )


BINARY_SENSORS: tuple[E3dcBinarySensorDescription, ...] = (
    _ems_flag("charging_locked", EmsStatus.CHARGING_LOCKED),
    _ems_flag("discharging_locked", EmsStatus.DISCHARGING_LOCKED),
    _ems_flag("emergency_power_ready", EmsStatus.EMERGENCY_POWER_READY),
    _ems_flag("charging_limited_by_forecast", EmsStatus.WEATHER_BASED_CHARGING),
    _ems_flag("feed_in_limited", EmsStatus.FEED_IN_LIMITED),
    _ems_flag("charge_lock_time", EmsStatus.CHARGE_LOCK_TIME, enabled=False),
    _ems_flag("discharge_lock_time", EmsStatus.DISCHARGE_LOCK_TIME, enabled=False),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: E3dcConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the E3/DC binary sensor platform."""
    coordinator = entry.runtime_data
    async_add_entities(
        E3dcBinarySensor(coordinator, description) for description in BINARY_SENSORS
    )


class E3dcBinarySensor(E3dcEntity, BinarySensorEntity):
    """Defines an E3/DC binary sensor."""

    entity_description: E3dcBinarySensorDescription

    @property
    @override
    def is_on(self) -> bool | None:
        return self.entity_description.value_fn(self.coordinator.device)
