"""Support for SolarEdge Modbus sensor entities."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from solaredged import Inverter, InverterStatus, SunSpecDID

from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfApparentPower,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfReactivePower,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import LOGGER
from .coordinator import SolarEdgeModbusConfigEntry
from .entity import SolarEdgeModbusInverterEntity

PARALLEL_UPDATES = 0

# Per-phase points only carry data on split- and three-phase inverters.
_MULTI_PHASE = (SunSpecDID.SPLIT_PHASE_INVERTER, SunSpecDID.THREE_PHASE_INVERTER)


@dataclass(frozen=True, kw_only=True)
class SolarEdgeModbusSensorEntityDescription(SensorEntityDescription):
    """Describes a SolarEdge Modbus sensor entity."""

    exists_fn: Callable[[Inverter], bool] = lambda _: True
    value_fn: Callable[[Inverter], StateType]


INVERTER_SENSORS: tuple[SolarEdgeModbusSensorEntityDescription, ...] = (
    SolarEdgeModbusSensorEntityDescription(
        key="ac_power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda inverter: inverter.ac_power,
    ),
    SolarEdgeModbusSensorEntityDescription(
        key="ac_energy",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda inverter: inverter.ac_energy,
    ),
    SolarEdgeModbusSensorEntityDescription(
        key="ac_current",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda inverter: inverter.ac_current,
    ),
    SolarEdgeModbusSensorEntityDescription(
        key="ac_current_phase_a",
        translation_key="current_phase_a",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=2,
        exists_fn=lambda inverter: inverter.did in _MULTI_PHASE,
        value_fn=lambda inverter: inverter.ac_current_a,
    ),
    SolarEdgeModbusSensorEntityDescription(
        key="ac_current_phase_b",
        translation_key="current_phase_b",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=2,
        exists_fn=lambda inverter: inverter.did in _MULTI_PHASE,
        value_fn=lambda inverter: inverter.ac_current_b,
    ),
    SolarEdgeModbusSensorEntityDescription(
        key="ac_current_phase_c",
        translation_key="current_phase_c",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=2,
        exists_fn=lambda inverter: inverter.did is SunSpecDID.THREE_PHASE_INVERTER,
        value_fn=lambda inverter: inverter.ac_current_c,
    ),
    SolarEdgeModbusSensorEntityDescription(
        key="ac_voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=1,
        exists_fn=lambda inverter: inverter.did is SunSpecDID.SINGLE_PHASE_INVERTER,
        value_fn=lambda inverter: inverter.ac_voltage_an,
    ),
    SolarEdgeModbusSensorEntityDescription(
        key="ac_voltage_phase_ab",
        translation_key="voltage_phase_ab",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=1,
        exists_fn=lambda inverter: inverter.did in _MULTI_PHASE,
        value_fn=lambda inverter: inverter.ac_voltage_ab,
    ),
    SolarEdgeModbusSensorEntityDescription(
        key="ac_voltage_phase_bc",
        translation_key="voltage_phase_bc",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=1,
        exists_fn=lambda inverter: inverter.did is SunSpecDID.THREE_PHASE_INVERTER,
        value_fn=lambda inverter: inverter.ac_voltage_bc,
    ),
    SolarEdgeModbusSensorEntityDescription(
        key="ac_voltage_phase_ca",
        translation_key="voltage_phase_ca",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=1,
        exists_fn=lambda inverter: inverter.did is SunSpecDID.THREE_PHASE_INVERTER,
        value_fn=lambda inverter: inverter.ac_voltage_ca,
    ),
    SolarEdgeModbusSensorEntityDescription(
        key="ac_voltage_phase_an",
        translation_key="voltage_phase_an",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=1,
        exists_fn=lambda inverter: inverter.did in _MULTI_PHASE,
        value_fn=lambda inverter: inverter.ac_voltage_an,
    ),
    SolarEdgeModbusSensorEntityDescription(
        key="ac_voltage_phase_bn",
        translation_key="voltage_phase_bn",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=1,
        exists_fn=lambda inverter: inverter.did in _MULTI_PHASE,
        value_fn=lambda inverter: inverter.ac_voltage_bn,
    ),
    SolarEdgeModbusSensorEntityDescription(
        key="ac_voltage_phase_cn",
        translation_key="voltage_phase_cn",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=1,
        exists_fn=lambda inverter: inverter.did is SunSpecDID.THREE_PHASE_INVERTER,
        value_fn=lambda inverter: inverter.ac_voltage_cn,
    ),
    SolarEdgeModbusSensorEntityDescription(
        key="dc_power",
        translation_key="dc_power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda inverter: inverter.dc_power,
    ),
    SolarEdgeModbusSensorEntityDescription(
        key="dc_current",
        translation_key="dc_current",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=2,
        value_fn=lambda inverter: inverter.dc_current,
    ),
    SolarEdgeModbusSensorEntityDescription(
        key="dc_voltage",
        translation_key="dc_voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=1,
        value_fn=lambda inverter: inverter.dc_voltage,
    ),
    SolarEdgeModbusSensorEntityDescription(
        key="ac_frequency",
        device_class=SensorDeviceClass.FREQUENCY,
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        suggested_display_precision=2,
        value_fn=lambda inverter: inverter.ac_frequency,
    ),
    SolarEdgeModbusSensorEntityDescription(
        key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=1,
        value_fn=lambda inverter: inverter.temperature_heatsink,
    ),
    SolarEdgeModbusSensorEntityDescription(
        key="ac_apparent_power",
        device_class=SensorDeviceClass.APPARENT_POWER,
        native_unit_of_measurement=UnitOfApparentPower.VOLT_AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda inverter: inverter.ac_va,
    ),
    SolarEdgeModbusSensorEntityDescription(
        key="ac_reactive_power",
        device_class=SensorDeviceClass.REACTIVE_POWER,
        native_unit_of_measurement=UnitOfReactivePower.VOLT_AMPERE_REACTIVE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda inverter: inverter.ac_var,
    ),
    SolarEdgeModbusSensorEntityDescription(
        key="ac_power_factor",
        device_class=SensorDeviceClass.POWER_FACTOR,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        suggested_display_precision=1,
        value_fn=lambda inverter: inverter.ac_power_factor,
    ),
    SolarEdgeModbusSensorEntityDescription(
        key="status",
        translation_key="inverter_status",
        device_class=SensorDeviceClass.ENUM,
        options=[status.name.lower() for status in InverterStatus],
        value_fn=lambda inverter: (
            inverter.status.name.lower() if inverter.status else None
        ),
    ),
    SolarEdgeModbusSensorEntityDescription(
        key="vendor_status",
        translation_key="vendor_status",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda inverter: inverter.vendor_status,
    ),
)


def _inverter_sensor(
    entry: SolarEdgeModbusConfigEntry,
    description: SolarEdgeModbusSensorEntityDescription,
) -> SensorEntity:
    """Build an inverter sensor, monotonic where its state class asks for it."""
    if description.state_class is SensorStateClass.TOTAL_INCREASING:
        return SolarEdgeModbusInverterEnergySensorEntity(
            entry=entry, description=description
        )
    return SolarEdgeModbusInverterSensorEntity(entry=entry, description=description)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SolarEdgeModbusConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up SolarEdge Modbus sensor entities based on a config entry."""
    solaredge = entry.runtime_data.solaredge

    async_add_entities(
        _inverter_sensor(entry, description)
        for description in INVERTER_SENSORS
        if description.exists_fn(solaredge.inverter)
    )


class SolarEdgeModbusInverterSensorEntity(SolarEdgeModbusInverterEntity, SensorEntity):
    """Defines a SolarEdge Modbus inverter sensor entity."""

    entity_description: SolarEdgeModbusSensorEntityDescription

    @property
    @override
    def native_value(self) -> StateType:
        """Return the sensor value."""
        return self.entity_description.value_fn(self.coordinator.solaredge.inverter)


class SolarEdgeModbusEnergySensorEntity(RestoreSensor):
    """Keeps a lifetime-energy sensor monotonic across glitches and restarts.

    SolarEdge accumulators transiently report lower values (or zero) around
    the inverter's sleep/wake transition; a single such sample fed to a
    ``total_increasing`` sensor registers as a meter reset and corrupts the
    long-term statistics. The highest value seen wins, and it is restored
    across restarts so an overnight restart does not lose that truth.
    """

    _highest_value: float | None = None
    _glitch_logged = False

    @override
    async def async_added_to_hass(self) -> None:
        """Restore the highest previously seen value."""
        await super().async_added_to_hass()

        data = await self.async_get_last_sensor_data()
        if data is not None and isinstance(data.native_value, (int, float)):
            self._highest_value = data.native_value

    @property
    @override
    def native_value(self) -> StateType:
        """Return the sensor value, never lower than seen before."""
        value = super().native_value
        if not isinstance(value, (int, float)):
            return self._highest_value

        if self._highest_value is None or value >= self._highest_value:
            self._highest_value = value
            self._glitch_logged = False
            return value

        if not self._glitch_logged:
            LOGGER.warning(
                (
                    "%s reported a lifetime energy of %s Wh, lower than the"
                    " %s Wh seen before; ignoring the lower value (a known"
                    " SolarEdge glitch around its sleep/wake transition)"
                ),
                self.entity_id,
                value,
                self._highest_value,
            )
            self._glitch_logged = True

        return self._highest_value


class SolarEdgeModbusInverterEnergySensorEntity(
    SolarEdgeModbusEnergySensorEntity, SolarEdgeModbusInverterSensorEntity
):
    """Defines a monotonic SolarEdge Modbus inverter energy sensor entity."""
