"""Support for Fronius devices."""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Final

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    POWER_VOLT_AMPERE_REACTIVE,
    EntityCategory,
    UnitOfApparentPower,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

if TYPE_CHECKING:
    from . import FroniusSolarNet
    from .coordinator import (
        FroniusCoordinatorBase,
        FroniusInverterUpdateCoordinator,
        FroniusLoggerUpdateCoordinator,
        FroniusMeterUpdateCoordinator,
        FroniusOhmpilotUpdateCoordinator,
        FroniusPowerFlowUpdateCoordinator,
        FroniusStorageUpdateCoordinator,
    )

ENERGY_VOLT_AMPERE_REACTIVE_HOUR: Final = "varh"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Fronius sensor entities based on a config entry."""
    solar_net: FroniusSolarNet = hass.data[DOMAIN][config_entry.entry_id]
    for inverter_coordinator in solar_net.inverter_coordinators:
        inverter_coordinator.add_entities_for_seen_keys(
            async_add_entities, InverterSensor
        )
    if solar_net.logger_coordinator is not None:
        solar_net.logger_coordinator.add_entities_for_seen_keys(
            async_add_entities, LoggerSensor
        )
    if solar_net.meter_coordinator is not None:
        solar_net.meter_coordinator.add_entities_for_seen_keys(
            async_add_entities, MeterSensor
        )
    if solar_net.ohmpilot_coordinator is not None:
        solar_net.ohmpilot_coordinator.add_entities_for_seen_keys(
            async_add_entities, OhmpilotSensor
        )
    if solar_net.power_flow_coordinator is not None:
        solar_net.power_flow_coordinator.add_entities_for_seen_keys(
            async_add_entities, PowerFlowSensor
        )
    if solar_net.storage_coordinator is not None:
        solar_net.storage_coordinator.add_entities_for_seen_keys(
            async_add_entities, StorageSensor
        )


@dataclass
class FroniusSensorEntityDescription(SensorEntityDescription):
    """Describes Fronius sensor entity."""

    default_value: StateType | None = None


INVERTER_ENTITY_DESCRIPTIONS: list[FroniusSensorEntityDescription] = [
    FroniusSensorEntityDescription(
        key="energy_day",
        name="Energy day",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    FroniusSensorEntityDescription(
        key="energy_year",
        name="Energy year",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    FroniusSensorEntityDescription(
        key="energy_total",
        name="Energy total",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    FroniusSensorEntityDescription(
        key="frequency_ac",
        name="Frequency AC",
        default_value=0,
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    FroniusSensorEntityDescription(
        key="current_ac",
        name="Current AC",
        default_value=0,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FroniusSensorEntityDescription(
        key="current_dc",
        name="Current DC",
        default_value=0,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:current-dc",
    ),
    FroniusSensorEntityDescription(
        key="current_dc_2",
        name="Current DC 2",
        default_value=0,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:current-dc",
    ),
    FroniusSensorEntityDescription(
        key="power_ac",
        name="Power AC",
        default_value=0,
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FroniusSensorEntityDescription(
        key="voltage_ac",
        name="Voltage AC",
        default_value=0,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    FroniusSensorEntityDescription(
        key="voltage_dc",
        name="Voltage DC",
        default_value=0,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:current-dc",
    ),
    FroniusSensorEntityDescription(
        key="voltage_dc_2",
        name="Voltage DC 2",
        default_value=0,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:current-dc",
    ),
    # device status entities
    FroniusSensorEntityDescription(
        key="inverter_state",
        name="Inverter state",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    FroniusSensorEntityDescription(
        key="error_code",
        name="Error code",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    FroniusSensorEntityDescription(
        key="status_code",
        name="Status code",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    FroniusSensorEntityDescription(
        key="led_state",
        name="LED state",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    FroniusSensorEntityDescription(
        key="led_color",
        name="LED color",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
]

LOGGER_ENTITY_DESCRIPTIONS: list[FroniusSensorEntityDescription] = [
    FroniusSensorEntityDescription(
        key="co2_factor",
        name="CO₂ factor",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:molecule-co2",
    ),
    FroniusSensorEntityDescription(
        key="cash_factor",
        name="Grid export tariff",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:cash-plus",
    ),
    FroniusSensorEntityDescription(
        key="delivery_factor",
        name="Grid import tariff",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:cash-minus",
    ),
]

METER_ENTITY_DESCRIPTIONS: list[FroniusSensorEntityDescription] = [
    FroniusSensorEntityDescription(
        key="current_ac_phase_1",
        name="Current AC phase 1",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    FroniusSensorEntityDescription(
        key="current_ac_phase_2",
        name="Current AC phase 2",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    FroniusSensorEntityDescription(
        key="current_ac_phase_3",
        name="Current AC phase 3",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    FroniusSensorEntityDescription(
        key="energy_reactive_ac_consumed",
        name="Energy reactive AC consumed",
        native_unit_of_measurement=ENERGY_VOLT_AMPERE_REACTIVE_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:lightning-bolt-outline",
        entity_registry_enabled_default=False,
    ),
    FroniusSensorEntityDescription(
        key="energy_reactive_ac_produced",
        name="Energy reactive AC produced",
        native_unit_of_measurement=ENERGY_VOLT_AMPERE_REACTIVE_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:lightning-bolt-outline",
        entity_registry_enabled_default=False,
    ),
    FroniusSensorEntityDescription(
        key="energy_real_ac_minus",
        name="Energy real AC minus",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
    ),
    FroniusSensorEntityDescription(
        key="energy_real_ac_plus",
        name="Energy real AC plus",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
    ),
    FroniusSensorEntityDescription(
        key="energy_real_consumed",
        name="Energy real consumed",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    FroniusSensorEntityDescription(
        key="energy_real_produced",
        name="Energy real produced",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    FroniusSensorEntityDescription(
        key="frequency_phase_average",
        name="Frequency phase average",
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FroniusSensorEntityDescription(
        key="meter_location",
        name="Meter location",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    FroniusSensorEntityDescription(
        key="power_apparent_phase_1",
        name="Power apparent phase 1",
        native_unit_of_measurement=UnitOfApparentPower.VOLT_AMPERE,
        device_class=SensorDeviceClass.APPARENT_POWER,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:flash-outline",
        entity_registry_enabled_default=False,
    ),
    FroniusSensorEntityDescription(
        key="power_apparent_phase_2",
        name="Power apparent phase 2",
        native_unit_of_measurement=UnitOfApparentPower.VOLT_AMPERE,
        device_class=SensorDeviceClass.APPARENT_POWER,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:flash-outline",
        entity_registry_enabled_default=False,
    ),
    FroniusSensorEntityDescription(
        key="power_apparent_phase_3",
        name="Power apparent phase 3",
        native_unit_of_measurement=UnitOfApparentPower.VOLT_AMPERE,
        device_class=SensorDeviceClass.APPARENT_POWER,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:flash-outline",
        entity_registry_enabled_default=False,
    ),
    FroniusSensorEntityDescription(
        key="power_apparent",
        name="Power apparent",
        native_unit_of_measurement=UnitOfApparentPower.VOLT_AMPERE,
        device_class=SensorDeviceClass.APPARENT_POWER,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:flash-outline",
        entity_registry_enabled_default=False,
    ),
    FroniusSensorEntityDescription(
        key="power_factor_phase_1",
        name="Power factor phase 1",
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    FroniusSensorEntityDescription(
        key="power_factor_phase_2",
        name="Power factor phase 2",
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    FroniusSensorEntityDescription(
        key="power_factor_phase_3",
        name="Power factor phase 3",
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    FroniusSensorEntityDescription(
        key="power_factor",
        name="Power factor",
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FroniusSensorEntityDescription(
        key="power_reactive_phase_1",
        name="Power reactive phase 1",
        native_unit_of_measurement=POWER_VOLT_AMPERE_REACTIVE,
        device_class=SensorDeviceClass.REACTIVE_POWER,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:flash-outline",
        entity_registry_enabled_default=False,
    ),
    FroniusSensorEntityDescription(
        key="power_reactive_phase_2",
        name="Power reactive phase 2",
        native_unit_of_measurement=POWER_VOLT_AMPERE_REACTIVE,
        device_class=SensorDeviceClass.REACTIVE_POWER,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:flash-outline",
        entity_registry_enabled_default=False,
    ),
    FroniusSensorEntityDescription(
        key="power_reactive_phase_3",
        name="Power reactive phase 3",
        native_unit_of_measurement=POWER_VOLT_AMPERE_REACTIVE,
        device_class=SensorDeviceClass.REACTIVE_POWER,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:flash-outline",
        entity_registry_enabled_default=False,
    ),
    FroniusSensorEntityDescription(
        key="power_reactive",
        name="Power reactive",
        native_unit_of_measurement=POWER_VOLT_AMPERE_REACTIVE,
        device_class=SensorDeviceClass.REACTIVE_POWER,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:flash-outline",
        entity_registry_enabled_default=False,
    ),
    FroniusSensorEntityDescription(
        key="power_real_phase_1",
        name="Power real phase 1",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    FroniusSensorEntityDescription(
        key="power_real_phase_2",
        name="Power real phase 2",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    FroniusSensorEntityDescription(
        key="power_real_phase_3",
        name="Power real phase 3",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    FroniusSensorEntityDescription(
        key="power_real",
        name="Power real",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FroniusSensorEntityDescription(
        key="voltage_ac_phase_1",
        name="Voltage AC phase 1",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    FroniusSensorEntityDescription(
        key="voltage_ac_phase_2",
        name="Voltage AC phase 2",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    FroniusSensorEntityDescription(
        key="voltage_ac_phase_3",
        name="Voltage AC phase 3",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    FroniusSensorEntityDescription(
        key="voltage_ac_phase_to_phase_12",
        name="Voltage AC phase 1-2",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    FroniusSensorEntityDescription(
        key="voltage_ac_phase_to_phase_23",
        name="Voltage AC phase 2-3",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    FroniusSensorEntityDescription(
        key="voltage_ac_phase_to_phase_31",
        name="Voltage AC phase 3-1",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
]

OHMPILOT_ENTITY_DESCRIPTIONS: list[FroniusSensorEntityDescription] = [
    FroniusSensorEntityDescription(
        key="energy_real_ac_consumed",
        name="Energy consumed",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    FroniusSensorEntityDescription(
        key="power_real_ac",
        name="Power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FroniusSensorEntityDescription(
        key="temperature_channel_1",
        name="Temperature channel 1",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FroniusSensorEntityDescription(
        key="error_code",
        name="Error code",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    FroniusSensorEntityDescription(
        key="state_code",
        name="State code",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    FroniusSensorEntityDescription(
        key="state_message",
        name="State message",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
]

POWER_FLOW_ENTITY_DESCRIPTIONS: list[FroniusSensorEntityDescription] = [
    FroniusSensorEntityDescription(
        key="energy_day",
        name="Energy day",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
    ),
    FroniusSensorEntityDescription(
        key="energy_year",
        name="Energy year",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
    ),
    FroniusSensorEntityDescription(
        key="energy_total",
        name="Energy total",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
    ),
    FroniusSensorEntityDescription(
        key="meter_mode",
        name="Meter mode",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    FroniusSensorEntityDescription(
        key="power_battery",
        name="Power battery",
        default_value=0,
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FroniusSensorEntityDescription(
        key="power_grid",
        name="Power grid",
        default_value=0,
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FroniusSensorEntityDescription(
        key="power_load",
        name="Power load",
        default_value=0,
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FroniusSensorEntityDescription(
        key="power_photovoltaics",
        name="Power photovoltaics",
        default_value=0,
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FroniusSensorEntityDescription(
        key="relative_autonomy",
        name="Relative autonomy",
        default_value=0,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:home-circle-outline",
    ),
    FroniusSensorEntityDescription(
        key="relative_self_consumption",
        name="Relative self consumption",
        default_value=0,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:solar-power",
    ),
]

STORAGE_ENTITY_DESCRIPTIONS: list[FroniusSensorEntityDescription] = [
    FroniusSensorEntityDescription(
        key="capacity_maximum",
        name="Capacity maximum",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    FroniusSensorEntityDescription(
        key="capacity_designed",
        name="Capacity designed",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    FroniusSensorEntityDescription(
        key="current_dc",
        name="Current DC",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:current-dc",
    ),
    FroniusSensorEntityDescription(
        key="voltage_dc",
        name="Voltage DC",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:current-dc",
    ),
    FroniusSensorEntityDescription(
        key="voltage_dc_maximum_cell",
        name="Voltage DC maximum cell",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:current-dc",
        entity_registry_enabled_default=False,
    ),
    FroniusSensorEntityDescription(
        key="voltage_dc_minimum_cell",
        name="Voltage DC minimum cell",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:current-dc",
        entity_registry_enabled_default=False,
    ),
    FroniusSensorEntityDescription(
        key="state_of_charge",
        name="State of charge",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FroniusSensorEntityDescription(
        key="temperature_cell",
        name="Temperature cell",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
]


class _FroniusSensorEntity(CoordinatorEntity["FroniusCoordinatorBase"], SensorEntity):
    """Defines a Fronius coordinator entity."""

    entity_description: FroniusSensorEntityDescription
    entity_descriptions: list[FroniusSensorEntityDescription]

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: FroniusCoordinatorBase,
        key: str,
        solar_net_id: str,
    ) -> None:
        """Set up an individual Fronius meter sensor."""
        super().__init__(coordinator)
        self.entity_description = next(
            desc for desc in self.entity_descriptions if desc.key == key
        )
        self.solar_net_id = solar_net_id
        self._attr_native_value = self._get_entity_value()

    def _device_data(self) -> dict[str, Any]:
        """Extract information for SolarNet device from coordinator data."""
        return self.coordinator.data[self.solar_net_id]

    def _get_entity_value(self) -> Any:
        """Extract entity value from coordinator. Raises KeyError if not included in latest update."""
        try:
            new_value = self.coordinator.data[self.solar_net_id][
                self.entity_description.key
            ]["value"]
        except KeyError:
            if self.entity_description.default_value is None:
                raise
            return self.entity_description.default_value
        if new_value is None:
            return self.entity_description.default_value
        return round(new_value, 4) if isinstance(new_value, float) else new_value

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        try:
            self._attr_native_value = self._get_entity_value()
        except KeyError:
            return
        self.async_write_ha_state()


class InverterSensor(_FroniusSensorEntity):
    """Defines a Fronius inverter device sensor entity."""

    entity_descriptions = INVERTER_ENTITY_DESCRIPTIONS

    def __init__(
        self,
        coordinator: FroniusInverterUpdateCoordinator,
        key: str,
        solar_net_id: str,
    ) -> None:
        """Set up an individual Fronius inverter sensor."""
        super().__init__(coordinator, key, solar_net_id)
        # device_info created in __init__ from a `GetInverterInfo` request
        self._attr_device_info = coordinator.inverter_info.device_info
        self._attr_unique_id = f"{coordinator.inverter_info.unique_id}-{key}"


class LoggerSensor(_FroniusSensorEntity):
    """Defines a Fronius logger device sensor entity."""

    entity_descriptions = LOGGER_ENTITY_DESCRIPTIONS

    def __init__(
        self,
        coordinator: FroniusLoggerUpdateCoordinator,
        key: str,
        solar_net_id: str,
    ) -> None:
        """Set up an individual Fronius meter sensor."""
        super().__init__(coordinator, key, solar_net_id)
        logger_data = self._device_data()
        # Logger device is already created in FroniusSolarNet._create_solar_net_device
        self._attr_device_info = coordinator.solar_net.system_device_info
        self._attr_native_unit_of_measurement = logger_data[key].get("unit")
        self._attr_unique_id = f'{logger_data["unique_identifier"]["value"]}-{key}'


class MeterSensor(_FroniusSensorEntity):
    """Defines a Fronius meter device sensor entity."""

    entity_descriptions = METER_ENTITY_DESCRIPTIONS

    def __init__(
        self,
        coordinator: FroniusMeterUpdateCoordinator,
        key: str,
        solar_net_id: str,
    ) -> None:
        """Set up an individual Fronius meter sensor."""
        super().__init__(coordinator, key, solar_net_id)
        meter_data = self._device_data()
        # S0 meters connected directly to inverters respond "n.a." as serial number
        # `model` contains the inverter id: "S0 Meter at inverter 1"
        if (meter_uid := meter_data["serial"]["value"]) == "n.a.":
            meter_uid = (
                f"{coordinator.solar_net.solar_net_device_id}:"
                f'{meter_data["model"]["value"]}'
            )

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, meter_uid)},
            manufacturer=meter_data["manufacturer"]["value"],
            model=meter_data["model"]["value"],
            name=meter_data["model"]["value"],
            via_device=(DOMAIN, coordinator.solar_net.solar_net_device_id),
        )
        self._attr_unique_id = f"{meter_uid}-{key}"


class OhmpilotSensor(_FroniusSensorEntity):
    """Defines a Fronius Ohmpilot sensor entity."""

    entity_descriptions = OHMPILOT_ENTITY_DESCRIPTIONS

    def __init__(
        self,
        coordinator: FroniusOhmpilotUpdateCoordinator,
        key: str,
        solar_net_id: str,
    ) -> None:
        """Set up an individual Fronius meter sensor."""
        super().__init__(coordinator, key, solar_net_id)
        device_data = self._device_data()

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_data["serial"]["value"])},
            manufacturer=device_data["manufacturer"]["value"],
            model=f"{device_data['model']['value']} {device_data['hardware']['value']}",
            name=device_data["model"]["value"],
            sw_version=device_data["software"]["value"],
            via_device=(DOMAIN, coordinator.solar_net.solar_net_device_id),
        )
        self._attr_unique_id = f'{device_data["serial"]["value"]}-{key}'


class PowerFlowSensor(_FroniusSensorEntity):
    """Defines a Fronius power flow sensor entity."""

    entity_descriptions = POWER_FLOW_ENTITY_DESCRIPTIONS

    def __init__(
        self,
        coordinator: FroniusPowerFlowUpdateCoordinator,
        key: str,
        solar_net_id: str,
    ) -> None:
        """Set up an individual Fronius power flow sensor."""
        super().__init__(coordinator, key, solar_net_id)
        # SolarNet device is already created in FroniusSolarNet._create_solar_net_device
        self._attr_device_info = coordinator.solar_net.system_device_info
        self._attr_unique_id = (
            f"{coordinator.solar_net.solar_net_device_id}-power_flow-{key}"
        )


class StorageSensor(_FroniusSensorEntity):
    """Defines a Fronius storage device sensor entity."""

    entity_descriptions = STORAGE_ENTITY_DESCRIPTIONS

    def __init__(
        self,
        coordinator: FroniusStorageUpdateCoordinator,
        key: str,
        solar_net_id: str,
    ) -> None:
        """Set up an individual Fronius storage sensor."""
        super().__init__(coordinator, key, solar_net_id)
        storage_data = self._device_data()

        self._attr_unique_id = f'{storage_data["serial"]["value"]}-{key}'
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, storage_data["serial"]["value"])},
            manufacturer=storage_data["manufacturer"]["value"],
            model=storage_data["model"]["value"],
            name=storage_data["model"]["value"],
            via_device=(DOMAIN, coordinator.solar_net.solar_net_device_id),
        )
