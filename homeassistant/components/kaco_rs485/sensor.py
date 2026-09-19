"""Sensors.

Two commands feed these: `0` for the electrical values, `3` for the counters.
An inverter that answered one but not the other reports `None` for the other.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from kaco_rs485 import STATUS_OPTIONS, InverterState, status_slug

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfEnergy, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_ADDRESSES
from .coordinator import KacoRs485ConfigEntry, KacoRs485Coordinator
from .entity import KacoRs485Entity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class KacoSensorDescription(SensorEntityDescription):
    """A sensor plus how to pull its value out of an InverterState."""

    value_fn: Callable[[InverterState], float | str | None]


SENSORS: tuple[KacoSensorDescription, ...] = (
    KacoSensorDescription(
        key="ac_power",
        translation_key="ac_power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda s: s.measured.ac_power_w if s.measured else None,
    ),
    KacoSensorDescription(
        key="daily_yield",
        translation_key="daily_yield",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=0,
        value_fn=lambda s: s.measured.daily_yield_wh if s.measured else None,
    ),
    KacoSensorDescription(
        key="total_yield",
        translation_key="total_yield",
        device_class=SensorDeviceClass.ENERGY,
        # kWh on xi; the same field is Wh on blueplanet, which discovery rejects.
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda s: s.totals.total_yield_raw if s.totals else None,
    ),
    KacoSensorDescription(
        key="status",
        translation_key="status",
        device_class=SensorDeviceClass.ENUM,
        options=list(STATUS_OPTIONS),
        value_fn=lambda s: status_slug(s.measured.status) if s.measured else None,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: KacoRs485ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensors for every configured inverter."""
    coordinator = entry.runtime_data
    async_add_entities(
        KacoRs485Sensor(coordinator, address, description)
        for address in entry.data[CONF_ADDRESSES]
        for description in SENSORS
    )


class KacoRs485Sensor(KacoRs485Entity, SensorEntity):
    """One reading from one inverter."""

    entity_description: KacoSensorDescription

    def __init__(
        self,
        coordinator: KacoRs485Coordinator,
        address: int,
        description: KacoSensorDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, address)
        self.entity_description = description
        self._attr_unique_id = (
            f"{coordinator.config_entry.entry_id}_{address}_{description.key}"
        )

    @property
    @override
    def native_value(self) -> float | str | None:
        """Return the reading, or None if the inverter has not supplied it."""
        state = self.inverter
        return self.entity_description.value_fn(state) if state else None
