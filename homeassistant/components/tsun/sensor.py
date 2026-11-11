"""Sensors for TSUN micro-inverters."""

from dataclasses import replace
from typing import cast, override

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
    UnitOfFrequency,
    UnitOfPower,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import TsunConfigEntry
from .coordinator import TsunDataUpdateCoordinator
from .entity import TsunEntity

PARALLEL_UPDATES = 0


def _measurement(
    key: str,
    device_class: SensorDeviceClass,
    unit: str,
    *,
    suggested_display_precision: int,
    state_class: SensorStateClass = SensorStateClass.MEASUREMENT,
) -> SensorEntityDescription:
    return SensorEntityDescription(
        key=key,
        translation_key=key,
        device_class=device_class,
        native_unit_of_measurement=unit,
        state_class=state_class,
        suggested_display_precision=suggested_display_precision,
    )


SENSORS: tuple[SensorEntityDescription, ...] = (
    _measurement(
        "ac_voltage",
        SensorDeviceClass.VOLTAGE,
        UnitOfElectricPotential.VOLT,
        suggested_display_precision=1,
    ),
    _measurement(
        "ac_current",
        SensorDeviceClass.CURRENT,
        UnitOfElectricCurrent.AMPERE,
        suggested_display_precision=2,
    ),
    _measurement(
        "ac_frequency",
        SensorDeviceClass.FREQUENCY,
        UnitOfFrequency.HERTZ,
        suggested_display_precision=2,
    ),
    _measurement(
        "ac_power",
        SensorDeviceClass.POWER,
        UnitOfPower.WATT,
        suggested_display_precision=1,
    ),
    _measurement(
        "dc_power_total",
        SensorDeviceClass.POWER,
        UnitOfPower.WATT,
        suggested_display_precision=1,
    ),
    _measurement(
        "ac_energy_today",
        SensorDeviceClass.ENERGY,
        UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=2,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    _measurement(
        "ac_energy_total",
        SensorDeviceClass.ENERGY,
        UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=2,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
)


PV_SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    _measurement(
        "voltage",
        SensorDeviceClass.VOLTAGE,
        UnitOfElectricPotential.VOLT,
        suggested_display_precision=1,
    ),
    _measurement(
        "current",
        SensorDeviceClass.CURRENT,
        UnitOfElectricCurrent.AMPERE,
        suggested_display_precision=2,
    ),
    _measurement(
        "power",
        SensorDeviceClass.POWER,
        UnitOfPower.WATT,
        suggested_display_precision=1,
    ),
    _measurement(
        "energy_today",
        SensorDeviceClass.ENERGY,
        UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=2,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    _measurement(
        "energy_total",
        SensorDeviceClass.ENERGY,
        UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=2,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
)


def _pv_sensors(pv_count: int) -> tuple[SensorEntityDescription, ...]:
    descriptions: list[SensorEntityDescription] = []
    for number in range(1, pv_count + 1):
        descriptions.extend(
            replace(
                description,
                key=f"pv{number}_{description.key}",
                translation_placeholders={"pv_input": str(number)},
            )
            for description in PV_SENSOR_TYPES
        )
    return tuple(descriptions)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TsunConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up all measurements supported by the detected protocol."""
    coordinator = entry.runtime_data
    descriptions = (
        *SENSORS,
        *_pv_sensors(coordinator.data.device.pv_count),
    )
    async_add_entities(
        TsunSensor(coordinator, entry, description)
        for description in descriptions
        if description.key in coordinator.data.values
    )


class TsunSensor(TsunEntity, SensorEntity):
    """A TSUN sensor."""

    entity_description: SensorEntityDescription

    def __init__(
        self,
        coordinator: TsunDataUpdateCoordinator,
        entry: TsunConfigEntry,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize a TSUN sensor."""
        super().__init__(coordinator, entry)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.data.device.logger_sn}_{description.key}"

    @property
    @override
    def native_value(self) -> StateType:
        """Return the latest measurement."""
        return cast(
            StateType,
            self.coordinator.data.values.get(self.entity_description.key),
        )
