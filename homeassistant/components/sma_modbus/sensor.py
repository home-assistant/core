"""Support for SMA sensors."""

from dataclasses import dataclass
from enum import IntEnum
from typing import Final, override

from sma_modbus import DeviceType
from sma_modbus.home_manager import SystemStatus
from sma_modbus.sunny_boy_smart_energy import BatteryHealth, CmpBmsStatus

from homeassistant.components.sensor import (
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
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import SmaConfigEntry
from .const import UnitOfElectricResistance
from .coordinator import SmaCoordinator
from .entity import SmaEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True)
class SmaSensorEntityDescription(SensorEntityDescription):
    """Describes an SMA sensor entity.

    ``key`` is the attribute name on the library device component. The
    ``translation_key`` defaults to ``key`` so entity names resolve through
    ``strings.json`` automatically.
    """

    def __post_init__(self) -> None:
        """Set translation_key default to the entity key."""
        if self.translation_key is None:
            object.__setattr__(self, "translation_key", self.key)


def _energy(
    key: str,
    suggested_unit: str = UnitOfEnergy.KILO_WATT_HOUR,
    entity_category: EntityCategory | None = None,
    enabled_default: bool = True,
) -> SmaSensorEntityDescription:
    return SmaSensorEntityDescription(
        key=key,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_unit_of_measurement=suggested_unit,
        entity_category=entity_category,
        entity_registry_enabled_default=enabled_default,
    )


def _power(
    key: str,
    entity_category: EntityCategory | None = None,
    enabled_default: bool = True,
) -> SmaSensorEntityDescription:
    return SmaSensorEntityDescription(
        key=key,
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=entity_category,
        entity_registry_enabled_default=enabled_default,
    )


def _battery(
    key: str,
    entity_category: EntityCategory | None = None,
    enabled_default: bool = True,
) -> SmaSensorEntityDescription:
    return SmaSensorEntityDescription(
        key=key,
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=entity_category,
        entity_registry_enabled_default=enabled_default,
    )


def _voltage(
    key: str,
    entity_category: EntityCategory | None = None,
    enabled_default: bool = True,
) -> SmaSensorEntityDescription:
    return SmaSensorEntityDescription(
        key=key,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        entity_category=entity_category,
        entity_registry_enabled_default=enabled_default,
    )


def _current(
    key: str,
    suggested_unit: str | None = None,
    entity_category: EntityCategory | None = None,
    enabled_default: bool = True,
) -> SmaSensorEntityDescription:
    return SmaSensorEntityDescription(
        key=key,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        suggested_unit_of_measurement=suggested_unit,
        entity_category=entity_category,
        entity_registry_enabled_default=enabled_default,
    )


def _frequency(
    key: str,
    entity_category: EntityCategory | None = None,
    enabled_default: bool = True,
) -> SmaSensorEntityDescription:
    return SmaSensorEntityDescription(
        key=key,
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        entity_category=entity_category,
        entity_registry_enabled_default=enabled_default,
    )


def _temperature(
    key: str,
    entity_category: EntityCategory | None = None,
    enabled_default: bool = True,
) -> SmaSensorEntityDescription:
    return SmaSensorEntityDescription(
        key=key,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        entity_category=entity_category,
        entity_registry_enabled_default=enabled_default,
    )


def _apparent_power(
    key: str,
    entity_category: EntityCategory | None = None,
    enabled_default: bool = True,
) -> SmaSensorEntityDescription:
    return SmaSensorEntityDescription(
        key=key,
        native_unit_of_measurement=UnitOfApparentPower.VOLT_AMPERE,
        device_class=SensorDeviceClass.APPARENT_POWER,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=entity_category,
        entity_registry_enabled_default=enabled_default,
    )


def _reactive_power(
    key: str,
    entity_category: EntityCategory | None = None,
    enabled_default: bool = True,
) -> SmaSensorEntityDescription:
    return SmaSensorEntityDescription(
        key=key,
        native_unit_of_measurement=UnitOfReactivePower.VOLT_AMPERE_REACTIVE,
        device_class=SensorDeviceClass.REACTIVE_POWER,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=entity_category,
        entity_registry_enabled_default=enabled_default,
    )


def _power_factor(
    key: str,
    entity_category: EntityCategory | None = None,
    enabled_default: bool = True,
) -> SmaSensorEntityDescription:
    return SmaSensorEntityDescription(
        key=key,
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
        entity_category=entity_category,
        entity_registry_enabled_default=enabled_default,
    )


def _enum(
    key: str,
    enum_type: type[IntEnum],
    entity_category: EntityCategory | None = None,
    enabled_default: bool = True,
) -> SmaSensorEntityDescription:
    """Create an ENUM sensor description for a typed status field.

    The library returns an ``IntEnum`` member (or ``None`` on the sentinel);
    the entity converts it to the member's lowercase ``.name`` so Home
    Assistant stores the state as a string from ``options``. Translation keys
    must be ``[a-z0-9-_]+``.
    """
    return SmaSensorEntityDescription(
        key=key,
        device_class=SensorDeviceClass.ENUM,
        options=[member.name.lower() for member in enum_type],
        entity_category=entity_category,
        entity_registry_enabled_default=enabled_default,
    )


def _ohm(
    key: str,
    entity_category: EntityCategory | None = None,
    enabled_default: bool = True,
) -> SmaSensorEntityDescription:
    return SmaSensorEntityDescription(
        key=key,
        native_unit_of_measurement=UnitOfElectricResistance.OHM,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=entity_category,
        entity_registry_enabled_default=enabled_default,
    )


SENSOR_DESCRIPTIONS: Final[dict[DeviceType, list[SmaSensorEntityDescription]]] = {
    DeviceType.SUNNY_HOME_MANAGER: [
        _enum("system_status", SystemStatus),
        _energy("grid_import_energy"),
        _energy("grid_export_energy"),
        _power("grid_import_power"),
        _power("grid_export_power"),
    ],
    DeviceType.SUNNY_BOY_SMART_ENERGY: [
        # System status
        _enum("system_status", SystemStatus, EntityCategory.DIAGNOSTIC),
        # PV
        _power("pv_power"),
        _energy("pv_energy_total"),
        # AC power
        _power("ac_power"),
        _power("ac_power_l1", enabled_default=False),
        _power("ac_power_l2", enabled_default=False),
        _power("ac_power_l3", enabled_default=False),
        # AC voltage
        _voltage("ac_voltage_l1"),
        _voltage("ac_voltage_l2"),
        _voltage("ac_voltage_l3"),
        _voltage("ac_voltage_l1_l2", enabled_default=False),
        _voltage("ac_voltage_l2_l3", enabled_default=False),
        _voltage("ac_voltage_l3_l1", enabled_default=False),
        # AC current
        _current("ac_current"),
        _current("ac_current_l1", enabled_default=False),
        _current("ac_current_l2", enabled_default=False),
        _current("ac_current_l3", enabled_default=False),
        # AC frequency
        _frequency("grid_frequency"),
        # AC reactive power
        _reactive_power("ac_reactive_power"),
        _reactive_power("ac_reactive_power_l1", enabled_default=False),
        _reactive_power("ac_reactive_power_l2", enabled_default=False),
        _reactive_power("ac_reactive_power_l3", enabled_default=False),
        # AC apparent power
        _apparent_power("ac_apparent_power", enabled_default=False),
        _apparent_power("ac_apparent_power_l1", enabled_default=False),
        _apparent_power("ac_apparent_power_l2", enabled_default=False),
        _apparent_power("ac_apparent_power_l3", enabled_default=False),
        # AC power factor
        _power_factor("power_factor", enabled_default=False),
        _power_factor("power_factor_eei"),
        # Battery
        _current("battery_current"),
        _battery("battery_state_of_charge"),
        _battery(
            "battery_nominal_capacity", EntityCategory.DIAGNOSTIC, enabled_default=False
        ),
        _temperature("battery_temperature", EntityCategory.DIAGNOSTIC),
        _voltage("battery_voltage"),
        _power("battery_charge_power"),
        _power("battery_discharge_power"),
        _energy("battery_charge_energy"),
        _energy("battery_discharge_energy"),
        _enum("battery_health", BatteryHealth, EntityCategory.DIAGNOSTIC),
        _voltage("battery_max_voltage", EntityCategory.DIAGNOSTIC),
        _temperature(
            "battery_temperature_max", EntityCategory.DIAGNOSTIC, enabled_default=False
        ),
        _temperature(
            "battery_temperature_min", EntityCategory.DIAGNOSTIC, enabled_default=False
        ),
        _voltage(
            "battery_end_of_charge_voltage",
            EntityCategory.DIAGNOSTIC,
            enabled_default=False,
        ),
        _voltage(
            "battery_end_of_discharge_voltage",
            EntityCategory.DIAGNOSTIC,
            enabled_default=False,
        ),
        _current(
            "battery_max_charge_current", entity_category=EntityCategory.DIAGNOSTIC
        ),
        _current(
            "battery_max_discharge_current", entity_category=EntityCategory.DIAGNOSTIC
        ),
        _voltage(
            "battery_cell_voltage_sum", EntityCategory.DIAGNOSTIC, enabled_default=False
        ),
        _voltage(
            "battery_cell_voltage_min", EntityCategory.DIAGNOSTIC, enabled_default=False
        ),
        _voltage(
            "battery_cell_voltage_max", EntityCategory.DIAGNOSTIC, enabled_default=False
        ),
        _enum("bms_operating_status", CmpBmsStatus, enabled_default=False),
        _energy("battery_current_charge_energy", enabled_default=False),
        _energy("battery_current_discharge_energy", enabled_default=False),
        # DC strings (0-based)
        _power("dc_power_0"),
        _power("dc_power_1"),
        _power("dc_power_2"),
        _energy("dc_energy_total_0", UnitOfEnergy.WATT_HOUR),
        _energy("dc_energy_total_1", UnitOfEnergy.WATT_HOUR),
        _energy("dc_energy_total_2", UnitOfEnergy.WATT_HOUR),
        _voltage("dc_voltage_0"),
        _voltage("dc_voltage_1"),
        _voltage("dc_voltage_2"),
        _current("dc_current_0"),
        _current("dc_current_1"),
        _current("dc_current_2"),
        # Insulation
        _ohm("insulation_resistance", EntityCategory.DIAGNOSTIC),
        _current(
            "insulation_residual_current",
            UnitOfElectricCurrent.MILLIAMPERE,
            EntityCategory.DIAGNOSTIC,
        ),
    ],
    DeviceType.SUNNY_BOY: [
        # System status
        _enum("system_status", SystemStatus, EntityCategory.DIAGNOSTIC),
        # PV
        _power("pv_power"),
        _energy("pv_energy_total"),
        # AC power
        _power("ac_power"),
        _power("ac_power_l1", enabled_default=False),
        _power("ac_power_l2", enabled_default=False),
        _power("ac_power_l3", enabled_default=False),
        # AC voltage
        _voltage("ac_voltage_l1"),
        _voltage("ac_voltage_l2"),
        _voltage("ac_voltage_l3"),
        _voltage("ac_voltage_l1_l2", enabled_default=False),
        _voltage("ac_voltage_l2_l3", enabled_default=False),
        _voltage("ac_voltage_l3_l1", enabled_default=False),
        # AC current
        _current("ac_current"),
        _current("ac_current_l1", enabled_default=False),
        _current("ac_current_l2", enabled_default=False),
        _current("ac_current_l3", enabled_default=False),
        # AC frequency
        _frequency("grid_frequency"),
        # AC reactive power
        _reactive_power("ac_reactive_power"),
        _reactive_power("ac_reactive_power_l1", enabled_default=False),
        _reactive_power("ac_reactive_power_l2", enabled_default=False),
        _reactive_power("ac_reactive_power_l3", enabled_default=False),
        # AC apparent power
        _apparent_power("ac_apparent_power", enabled_default=False),
        _apparent_power("ac_apparent_power_l1", enabled_default=False),
        _apparent_power("ac_apparent_power_l2", enabled_default=False),
        _apparent_power("ac_apparent_power_l3", enabled_default=False),
        # AC power factor
        _power_factor("power_factor", enabled_default=False),
        _power_factor("power_factor_eei"),
        # DC strings (0-based)
        _power("dc_power_0"),
        _power("dc_power_1"),
        _voltage("dc_voltage_0"),
        _voltage("dc_voltage_1"),
        _current("dc_current_0"),
        _current("dc_current_1"),
        # Insulation
        _ohm("insulation_resistance", EntityCategory.DIAGNOSTIC),
        _current(
            "insulation_residual_current",
            UnitOfElectricCurrent.MILLIAMPERE,
            EntityCategory.DIAGNOSTIC,
        ),
    ],
    DeviceType.SUNNY_TRIPOWER: [
        # System status
        _enum("system_status", SystemStatus, EntityCategory.DIAGNOSTIC),
        # Energy
        _energy("pv_energy_total"),
        _energy("grid_import_energy", enabled_default=False),
        _energy("grid_export_energy"),
        # AC power
        _power("ac_power"),
        _power("ac_power_l1", enabled_default=False),
        _power("ac_power_l2", enabled_default=False),
        _power("ac_power_l3", enabled_default=False),
        # Grid power
        _power("grid_import_power", enabled_default=False),
        _power("grid_export_power", enabled_default=False),
        # AC voltage
        _voltage("ac_voltage_l1"),
        _voltage("ac_voltage_l2"),
        _voltage("ac_voltage_l3"),
        _voltage("ac_voltage_l1_l2", enabled_default=False),
        _voltage("ac_voltage_l2_l3", enabled_default=False),
        _voltage("ac_voltage_l3_l1", enabled_default=False),
        # AC current
        _current("ac_current"),
        _current("ac_current_l1", enabled_default=False),
        _current("ac_current_l2", enabled_default=False),
        _current("ac_current_l3", enabled_default=False),
        # AC frequency
        _frequency("grid_frequency"),
        # AC reactive power
        _reactive_power("ac_reactive_power"),
        _reactive_power("ac_reactive_power_l1", enabled_default=False),
        _reactive_power("ac_reactive_power_l2", enabled_default=False),
        _reactive_power("ac_reactive_power_l3", enabled_default=False),
        # AC apparent power
        _apparent_power("ac_apparent_power", enabled_default=False),
        _apparent_power("ac_apparent_power_l1", enabled_default=False),
        _apparent_power("ac_apparent_power_l2", enabled_default=False),
        _apparent_power("ac_apparent_power_l3", enabled_default=False),
        # AC power factor
        _power_factor("power_factor", enabled_default=False),
        _power_factor("power_factor_eei"),
        # DC strings
        _power("dc_power_0"),
        _power("dc_power_1"),
        _voltage("dc_voltage_0"),
        _voltage("dc_voltage_1"),
        _current("dc_current_0"),
        _current("dc_current_1"),
        _current("dc_current_2", enabled_default=False),
        _current("dc_current_3", enabled_default=False),
        # Insulation
        _ohm("insulation_resistance", EntityCategory.DIAGNOSTIC),
        _current(
            "insulation_residual_current",
            UnitOfElectricCurrent.MILLIAMPERE,
            EntityCategory.DIAGNOSTIC,
        ),
        # Temperature
        _temperature("internal_temperature", EntityCategory.DIAGNOSTIC),
        # Intermediate circuit voltage
        _voltage(
            "intermediate_circuit_voltage",
            enabled_default=False,
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
    ],
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: SmaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up SMA sensor entities based on a config entry."""
    coordinator = config_entry.runtime_data
    descriptions = SENSOR_DESCRIPTIONS[coordinator.device_type]
    async_add_entities(
        SmaSensor(coordinator, description) for description in descriptions
    )


class SmaSensor(SmaEntity, SensorEntity):
    """Defines a SMA sensor entity."""

    entity_description: SmaSensorEntityDescription

    def __init__(
        self,
        coordinator: SmaCoordinator,
        description: SmaSensorEntityDescription,
    ) -> None:
        """Initialize a SMA sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.config_entry.unique_id}-{description.key}"  # type: ignore[union-attr]
        self._attr_native_value = self._read_value()

    def _read_value(self) -> StateType:
        """Read the field value from the device component."""
        value = getattr(self.device, self.entity_description.key)
        if isinstance(value, IntEnum):
            return value.name.lower()
        if isinstance(value, float):
            return round(value, 4)
        return value

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._attr_native_value = self._read_value()
        self.async_write_ha_state()
