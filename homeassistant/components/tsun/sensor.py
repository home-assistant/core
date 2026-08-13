"""Sensors for TSUN micro-inverters."""

from dataclasses import dataclass
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
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import TsunConfigEntry
from .coordinator import TsunDataUpdateCoordinator
from .entity import TsunEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class TsunSensorEntityDescription(SensorEntityDescription):
    """Describe a TSUN sensor."""


def _measurement(
    key: str,
    device_class: SensorDeviceClass,
    unit: str,
    precision: int,
    *,
    state_class: SensorStateClass = SensorStateClass.MEASUREMENT,
) -> TsunSensorEntityDescription:
    return TsunSensorEntityDescription(
        key=key,
        translation_key=key,
        device_class=device_class,
        native_unit_of_measurement=unit,
        state_class=state_class,
        suggested_display_precision=precision,
    )


SENSORS: tuple[TsunSensorEntityDescription, ...] = (
    _measurement(
        "ac_voltage", SensorDeviceClass.VOLTAGE, UnitOfElectricPotential.VOLT, 1
    ),
    _measurement(
        "ac_current", SensorDeviceClass.CURRENT, UnitOfElectricCurrent.AMPERE, 2
    ),
    _measurement("ac_frequency", SensorDeviceClass.FREQUENCY, UnitOfFrequency.HERTZ, 2),
    _measurement("ac_power", SensorDeviceClass.POWER, UnitOfPower.WATT, 1),
    _measurement("dc_power_total", SensorDeviceClass.POWER, UnitOfPower.WATT, 1),
    _measurement(
        "ac_energy_today",
        SensorDeviceClass.ENERGY,
        UnitOfEnergy.KILO_WATT_HOUR,
        2,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    _measurement(
        "ac_energy_total",
        SensorDeviceClass.ENERGY,
        UnitOfEnergy.KILO_WATT_HOUR,
        2,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
)


def _pv_sensors(pv_count: int) -> tuple[TsunSensorEntityDescription, ...]:
    descriptions: list[TsunSensorEntityDescription] = []
    for number in range(1, pv_count + 1):
        for suffix, device_class, unit, state_class, precision in (
            (
                "voltage",
                SensorDeviceClass.VOLTAGE,
                UnitOfElectricPotential.VOLT,
                SensorStateClass.MEASUREMENT,
                1,
            ),
            (
                "current",
                SensorDeviceClass.CURRENT,
                UnitOfElectricCurrent.AMPERE,
                SensorStateClass.MEASUREMENT,
                2,
            ),
            (
                "power",
                SensorDeviceClass.POWER,
                UnitOfPower.WATT,
                SensorStateClass.MEASUREMENT,
                1,
            ),
            (
                "energy_today",
                SensorDeviceClass.ENERGY,
                UnitOfEnergy.KILO_WATT_HOUR,
                SensorStateClass.TOTAL_INCREASING,
                2,
            ),
            (
                "energy_total",
                SensorDeviceClass.ENERGY,
                UnitOfEnergy.KILO_WATT_HOUR,
                SensorStateClass.TOTAL_INCREASING,
                2,
            ),
        ):
            key = f"pv{number}_{suffix}"
            descriptions.append(
                TsunSensorEntityDescription(
                    key=key,
                    translation_key=suffix,
                    translation_placeholders={"input": str(number)},
                    device_class=device_class,
                    native_unit_of_measurement=unit,
                    state_class=state_class,
                    suggested_display_precision=precision,
                )
            )
    return tuple(descriptions)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TsunConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up all measurements supported by the detected protocol."""
    coordinator = entry.runtime_data
    added_keys: set[str] = set()

    @callback
    def async_add_discovered_entities() -> None:
        """Add entities exposed after a successful poll."""
        values = coordinator.data.values
        descriptions = [
            description
            for description in (
                *SENSORS,
                *_pv_sensors(coordinator.data.device.pv_count),
            )
            if description.key not in added_keys and description.key in values
        ]
        if not descriptions:
            return
        added_keys.update(description.key for description in descriptions)
        async_add_entities(
            TsunSensor(coordinator, entry, description) for description in descriptions
        )

    async_add_discovered_entities()
    entry.async_on_unload(coordinator.async_add_listener(async_add_discovered_entities))


class TsunSensor(TsunEntity, SensorEntity):
    """A TSUN sensor."""

    entity_description: TsunSensorEntityDescription

    def __init__(
        self,
        coordinator: TsunDataUpdateCoordinator,
        entry: TsunConfigEntry,
        description: TsunSensorEntityDescription,
    ) -> None:
        """Initialize a TSUN sensor."""
        super().__init__(coordinator, entry)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.data.device.logger_sn}_{description.key}"

    @property
    @override
    def suggested_object_id(self) -> str:
        """Keep technical entity identifiers in English for every UI language."""
        return self.entity_description.key

    @property
    @override
    def native_value(self) -> StateType:
        """Return the latest measurement."""
        return cast(
            StateType,
            self.coordinator.data.values.get(self.entity_description.key),
        )
