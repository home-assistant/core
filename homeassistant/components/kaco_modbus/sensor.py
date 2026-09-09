"""What the inverter measures."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from kaco_modbus import KacoInverter
from kaco_modbus.models import InverterThreePhase

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
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

from .coordinator import KacoConfigEntry
from .entity import KacoEntity, KacoEntityDescription

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class KacoSensorDescription(SensorEntityDescription, KacoEntityDescription):
    """A sensor, and where to read its value off the inverter."""

    value_fn: Callable[[KacoInverter], StateType]


def _block(device: KacoInverter) -> InverterThreePhase:
    """The model 103 block, which setup requires, so it is always bound here."""
    assert device.inverter is not None
    return device.inverter


SENSOR_DESCRIPTIONS: tuple[KacoSensorDescription, ...] = (
    KacoSensorDescription(
        key="ac_power",
        component="inverter",
        translation_key="ac_power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda device: _block(device).w,
    ),
    KacoSensorDescription(
        key="lifetime_energy",
        component="inverter",
        translation_key="lifetime_energy",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=2,
        value_fn=lambda device: _block(device).wh,
    ),
    KacoSensorDescription(
        key="operating_state",
        component="inverter",
        translation_key="operating_state",
        device_class=SensorDeviceClass.ENUM,
        options=[
            "off",
            "sleeping",
            "starting",
            "mppt",
            "throttled",
            "shutting_down",
            "fault",
            "standby",
        ],
        value_fn=lambda device: (
            None if (state := _block(device).st) is None else state.name.lower()
        ),
    ),
    KacoSensorDescription(
        key="ac_current",
        component="inverter",
        translation_key="ac_current",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda device: _block(device).a,
    ),
    KacoSensorDescription(
        key="dc_power",
        component="inverter",
        translation_key="dc_power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda device: _block(device).dcw,
    ),
    KacoSensorDescription(
        key="temperature",
        component="inverter",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        # Parked at 0 degC while asleep, a plausible winter reading, so this
        # is gated on the operating state rather than on the value.
        value_fn=lambda device: device.temperature,
    ),
    KacoSensorDescription(
        key="apparent_power",
        component="inverter",
        device_class=SensorDeviceClass.APPARENT_POWER,
        native_unit_of_measurement=UnitOfApparentPower.VOLT_AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda device: _block(device).va,
    ),
    KacoSensorDescription(
        key="reactive_power",
        component="inverter",
        device_class=SensorDeviceClass.REACTIVE_POWER,
        native_unit_of_measurement=UnitOfReactivePower.VOLT_AMPERE_REACTIVE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda device: _block(device).v_ar,
    ),
    KacoSensorDescription(
        key="power_factor",
        component="inverter",
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        # Parked at 1.00 while asleep, though with no current flowing the
        # ratio is undefined.
        value_fn=lambda device: device.power_factor,
    ),
    KacoSensorDescription(
        key="frequency",
        component="inverter",
        translation_key="frequency",
        device_class=SensorDeviceClass.FREQUENCY,
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
        # Parked at 0 Hz while asleep, which reads as a grid outage.
        value_fn=lambda device: device.frequency,
    ),
    KacoSensorDescription(
        key="dc_voltage",
        component="inverter",
        translation_key="dc_voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        entity_registry_enabled_default=False,
        value_fn=lambda device: _block(device).dcv,
    ),
    KacoSensorDescription(
        key="dc_current",
        component="inverter",
        translation_key="dc_current",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda device: _block(device).dca,
    ),
    # Phase-to-neutral only: this firmware leaves the line-to-line voltages
    # unimplemented. The voltages are parked at 0 V while asleep; the phase
    # currents genuinely are zero, so only the voltages are gated.
    KacoSensorDescription(
        key="voltage_l1",
        component="inverter",
        translation_key="voltage_l1",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.phase_voltages[0],
    ),
    KacoSensorDescription(
        key="voltage_l2",
        component="inverter",
        translation_key="voltage_l2",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.phase_voltages[1],
    ),
    KacoSensorDescription(
        key="voltage_l3",
        component="inverter",
        translation_key="voltage_l3",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.phase_voltages[2],
    ),
    KacoSensorDescription(
        key="current_l1",
        component="inverter",
        translation_key="current_l1",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda device: _block(device).aph_a,
    ),
    KacoSensorDescription(
        key="current_l2",
        component="inverter",
        translation_key="current_l2",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda device: _block(device).aph_b,
    ),
    KacoSensorDescription(
        key="current_l3",
        component="inverter",
        translation_key="current_l3",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda device: _block(device).aph_c,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: KacoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the KACO Modbus sensor platform."""
    async_add_entities(
        KacoSensor(entry.runtime_data, description)
        for description in SENSOR_DESCRIPTIONS
    )


class KacoSensor(KacoEntity, SensorEntity):
    """A read-only value off the inverter."""

    entity_description: KacoSensorDescription

    @property
    @override
    def native_value(self) -> StateType:
        """Return the value this sensor reads from the device."""
        return self.entity_description.value_fn(self.coordinator.device)
