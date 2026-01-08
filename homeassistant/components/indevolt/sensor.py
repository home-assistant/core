"""Sensor platform for Indevolt integration."""

from dataclasses import dataclass, field
import logging
from typing import Final

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import IndevoltConfigEntry
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class IndevoltSensorEntityDescription(SensorEntityDescription):
    """Custom entity description class for Indevolt sensors."""

    coefficient: float = 1.0
    state_mapping: dict[int, str] = field(default_factory=dict)
    generation: list[int] = field(default_factory=lambda: [1, 2])


SENSORS: Final = (
    IndevoltSensorEntityDescription(
        key="0",
        generation=[1, 2],
        translation_key="serial_number",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    # System Operating Information
    IndevoltSensorEntityDescription(
        key="7101",
        generation=[1, 2],
        translation_key="working_mode",
        state_mapping={
            0: "outdoor_portable",
            1: "self_consumed_prioritized",
            4: "real_time_control",
            5: "charge_discharge_schedule",
        },
        device_class=SensorDeviceClass.ENUM,
    ),
    IndevoltSensorEntityDescription(
        key="142",
        generation=[2],
        translation_key="rated_capacity",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    IndevoltSensorEntityDescription(
        key="6105",
        generation=[1],
        translation_key="rated_capacity",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    IndevoltSensorEntityDescription(
        key="2101",
        generation=[1, 2],
        translation_key="total_ac_input_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    IndevoltSensorEntityDescription(
        key="2108",
        generation=[1, 2],
        translation_key="total_ac_output_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    IndevoltSensorEntityDescription(
        key="667",
        generation=[2],
        translation_key="bypass_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # Electrical Energy Information
    IndevoltSensorEntityDescription(
        key="2107",
        generation=[1],
        translation_key="total_ac_input_energy_gen1",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    IndevoltSensorEntityDescription(
        key="2107",
        generation=[2],
        translation_key="total_ac_output_energy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    IndevoltSensorEntityDescription(
        key="2104",
        generation=[2],
        translation_key="total_ac_input_energy",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    IndevoltSensorEntityDescription(
        key="2105",
        generation=[2],
        translation_key="off_grid_output_energy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    IndevoltSensorEntityDescription(
        key="11034",
        generation=[2],
        translation_key="bypass_input_energy",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    IndevoltSensorEntityDescription(
        key="6004",
        generation=[2],
        translation_key="battery_daily_charging_energy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    IndevoltSensorEntityDescription(
        key="6005",
        generation=[2],
        translation_key="battery_daily_discharging_energy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    IndevoltSensorEntityDescription(
        key="6006",
        generation=[2],
        translation_key="battery_total_charging_energy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    IndevoltSensorEntityDescription(
        key="6007",
        generation=[2],
        translation_key="battery_total_discharging_energy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    # Electricity Meter Status
    IndevoltSensorEntityDescription(
        key="7120",
        generation=[1, 2],
        translation_key="meter_connection_status",
        state_mapping={1000: "on", 1001: "off"},
        device_class=SensorDeviceClass.ENUM,
    ),
    IndevoltSensorEntityDescription(
        key="11016",
        generation=[2],
        translation_key="meter_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    IndevoltSensorEntityDescription(
        key="21028",
        generation=[1],
        translation_key="meter_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # Grid information
    IndevoltSensorEntityDescription(
        key="2600",
        generation=[2],
        translation_key="grid_voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    IndevoltSensorEntityDescription(
        key="2612",
        generation=[2],
        translation_key="grid_frequency",
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    # Battery Pack Operating Parameters
    IndevoltSensorEntityDescription(
        key="6000",
        generation=[1, 2],
        translation_key="battery_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    IndevoltSensorEntityDescription(
        key="6001",
        generation=[1, 2],
        translation_key="battery_charge_discharge_state",
        state_mapping={1000: "static", 1001: "charging", 1002: "discharging"},
        device_class=SensorDeviceClass.ENUM,
    ),
    IndevoltSensorEntityDescription(
        key="6002",
        generation=[1, 2],
        translation_key="battery_soc",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # PV Operating Parameters
    IndevoltSensorEntityDescription(
        key="1501",
        generation=[1, 2],
        translation_key="total_dc_output_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    IndevoltSensorEntityDescription(
        key="1502",
        generation=[1, 2],
        translation_key="daily_production",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    IndevoltSensorEntityDescription(
        key="1505",
        generation=[1],
        translation_key="cumulative_production",
        coefficient=0.001,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    IndevoltSensorEntityDescription(
        key="1632",
        generation=[2],
        translation_key="dc_input_current_1",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    IndevoltSensorEntityDescription(
        key="1600",
        generation=[2],
        translation_key="dc_input_voltage_1",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    IndevoltSensorEntityDescription(
        key="1664",
        generation=[1, 2],
        translation_key="dc_input_power_1",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    IndevoltSensorEntityDescription(
        key="1633",
        generation=[2],
        translation_key="dc_input_current_2",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    IndevoltSensorEntityDescription(
        key="1601",
        generation=[2],
        translation_key="dc_input_voltage_2",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    IndevoltSensorEntityDescription(
        key="1665",
        generation=[1, 2],
        translation_key="dc_input_power_2",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    IndevoltSensorEntityDescription(
        key="1634",
        generation=[2],
        translation_key="dc_input_current_3",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    IndevoltSensorEntityDescription(
        key="1602",
        generation=[2],
        translation_key="dc_input_voltage_3",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    IndevoltSensorEntityDescription(
        key="1666",
        generation=[2],
        translation_key="dc_input_power_3",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    IndevoltSensorEntityDescription(
        key="1635",
        generation=[2],
        translation_key="dc_input_current_4",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    IndevoltSensorEntityDescription(
        key="1603",
        generation=[2],
        translation_key="dc_input_voltage_4",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    IndevoltSensorEntityDescription(
        key="1667",
        generation=[2],
        translation_key="dc_input_power_4",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    # Battery Pack Serial Numbers
    IndevoltSensorEntityDescription(
        key="9008",
        generation=[2],
        translation_key="master_serial_number",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    IndevoltSensorEntityDescription(
        key="9032",
        generation=[2],
        translation_key="battery_pack_1_serial_number",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    IndevoltSensorEntityDescription(
        key="9051",
        generation=[2],
        translation_key="battery_pack_2_serial_number",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    IndevoltSensorEntityDescription(
        key="9070",
        generation=[2],
        translation_key="battery_pack_3_serial_number",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    IndevoltSensorEntityDescription(
        key="9165",
        generation=[2],
        translation_key="battery_pack_4_serial_number",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    IndevoltSensorEntityDescription(
        key="9218",
        generation=[2],
        translation_key="battery_pack_5_serial_number",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    # Battery Pack SOC
    IndevoltSensorEntityDescription(
        key="9000",
        generation=[2],
        translation_key="master_soc",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    IndevoltSensorEntityDescription(
        key="9016",
        generation=[2],
        translation_key="battery_pack_1_soc",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    IndevoltSensorEntityDescription(
        key="9035",
        generation=[2],
        translation_key="battery_pack_2_soc",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    IndevoltSensorEntityDescription(
        key="9054",
        generation=[2],
        translation_key="battery_pack_3_soc",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    IndevoltSensorEntityDescription(
        key="9149",
        generation=[2],
        translation_key="battery_pack_4_soc",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    IndevoltSensorEntityDescription(
        key="9202",
        generation=[2],
        translation_key="battery_pack_5_soc",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    # Battery Pack Temperature
    IndevoltSensorEntityDescription(
        key="9012",
        generation=[2],
        translation_key="master_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    IndevoltSensorEntityDescription(
        key="9030",
        generation=[2],
        translation_key="battery_pack_1_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    IndevoltSensorEntityDescription(
        key="9049",
        generation=[2],
        translation_key="battery_pack_2_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    IndevoltSensorEntityDescription(
        key="9068",
        generation=[2],
        translation_key="battery_pack_3_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    IndevoltSensorEntityDescription(
        key="9163",
        generation=[2],
        translation_key="battery_pack_4_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    IndevoltSensorEntityDescription(
        key="9216",
        generation=[2],
        translation_key="battery_pack_5_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    # Battery Pack Voltage
    IndevoltSensorEntityDescription(
        key="9004",
        generation=[2],
        translation_key="master_voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    IndevoltSensorEntityDescription(
        key="9020",
        generation=[2],
        translation_key="battery_pack_1_voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    IndevoltSensorEntityDescription(
        key="9039",
        generation=[2],
        translation_key="battery_pack_2_voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    IndevoltSensorEntityDescription(
        key="9058",
        generation=[2],
        translation_key="battery_pack_3_voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    IndevoltSensorEntityDescription(
        key="9153",
        generation=[2],
        translation_key="battery_pack_4_voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    IndevoltSensorEntityDescription(
        key="9206",
        generation=[2],
        translation_key="battery_pack_5_voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    # Battery Pack Current
    IndevoltSensorEntityDescription(
        key="9013",
        generation=[2],
        translation_key="master_current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    IndevoltSensorEntityDescription(
        key="19173",
        generation=[2],
        translation_key="battery_pack_1_current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    IndevoltSensorEntityDescription(
        key="19174",
        generation=[2],
        translation_key="battery_pack_2_current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    IndevoltSensorEntityDescription(
        key="19175",
        generation=[2],
        translation_key="battery_pack_3_current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    IndevoltSensorEntityDescription(
        key="19176",
        generation=[2],
        translation_key="battery_pack_4_current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    IndevoltSensorEntityDescription(
        key="19177",
        generation=[2],
        translation_key="battery_pack_5_current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IndevoltConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensor platform for Indevolt."""
    coordinator = entry.runtime_data
    device_gen = entry.data.get("generation", 1)

    entities = [
        IndevoltSensorEntity(coordinator=coordinator, description=description)
        for description in SENSORS
        if device_gen in description.generation
    ]

    async_add_entities(entities)


class IndevoltSensorEntity(CoordinatorEntity, SensorEntity):
    """Represents a sensor entity for Indevolt devices."""

    _attr_has_entity_name = True
    entity_description: IndevoltSensorEntityDescription

    def __init__(
        self, coordinator, description: IndevoltSensorEntityDescription
    ) -> None:
        """Initialize the Indevolt sensor entity."""
        super().__init__(coordinator)

        self.entity_description = description
        self._attr_unique_id = (
            f"{DOMAIN}_{coordinator.config_entry.entry_id}_{description.key}"
        )
        self._attr_device_info = coordinator.device_info

        if description.device_class == SensorDeviceClass.ENUM:
            self._attr_options = sorted(set(description.state_mapping.values()))

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            super().available and self.entity_description.key in self.coordinator.data
        )

    @property
    def native_value(self) -> str | int | float | None:
        """Return the current value of the sensor in its native unit."""
        raw_value = self.coordinator.data.get(self.entity_description.key)

        if raw_value is None:
            return None

        if self.entity_description.entity_category == EntityCategory.DIAGNOSTIC:
            return raw_value

        if self.entity_description.device_class == SensorDeviceClass.ENUM:
            return self.entity_description.state_mapping.get(raw_value)

        return raw_value * self.entity_description.coefficient
