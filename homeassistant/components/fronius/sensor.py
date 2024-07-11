"""Support for Fronius devices."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Final

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
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
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    SOLAR_NET_DISCOVERY_NEW,
    InverterStatusCodeOption,
    MeterLocationCodeOption,
    OhmPilotStateCodeOption,
    get_inverter_status_message,
    get_meter_location_description,
    get_ohmpilot_state_message,
)

if TYPE_CHECKING:
    from . import FroniusConfigEntry
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
    config_entry: FroniusConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Fronius sensor entities based on a config entry."""
    solar_net = config_entry.runtime_data

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

    @callback
    def async_add_new_entities(coordinator: FroniusInverterUpdateCoordinator) -> None:
        """Add newly found inverter entities."""
        coordinator.add_entities_for_seen_keys(async_add_entities, InverterSensor)

    config_entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            SOLAR_NET_DISCOVERY_NEW,
            async_add_new_entities,
        )
    )


@dataclass(frozen=True)
class FroniusSensorEntityDescription(SensorEntityDescription):
    """Describes Fronius sensor entity."""

    default_value: StateType | None = None
    # Gen24 devices may report 0 for total energy while doing firmware updates.
    # Handling such values shall mitigate spikes in delta calculations.
    invalid_when_falsy: bool = False
    response_key: str | None = None
    value_fn: Callable[[StateType], StateType] | None = None


INVERTER_ENTITY_DESCRIPTIONS: list[FroniusSensorEntityDescription] = [
    FroniusSensorEntityDescription(
        key="energy_day",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    FroniusSensorEntityDescription(
        key="energy_year",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    FroniusSensorEntityDescription(
        key="energy_total",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        invalid_when_falsy=True,
    ),
    FroniusSensorEntityDescription(
        key="frequency_ac",
        default_value=0,
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    FroniusSensorEntityDescription(
        key="current_ac",
        default_value=0,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FroniusSensorEntityDescription(
        key="current_dc",
        default_value=0,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FroniusSensorEntityDescription(
        key="current_dc_2",
        default_value=0,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FroniusSensorEntityDescription(
        key="power_ac",
        default_value=0,
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FroniusSensorEntityDescription(
        key="voltage_ac",
        default_value=0,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    FroniusSensorEntityDescription(
        key="voltage_dc",
        default_value=0,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FroniusSensorEntityDescription(
        key="voltage_dc_2",
        default_value=0,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # device status entities
    FroniusSensorEntityDescription(
        key="inverter_state",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    FroniusSensorEntityDescription(
        key="error_code",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    FroniusSensorEntityDescription(
        key="status_code",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    FroniusSensorEntityDescription(
        key="status_message",
        response_key="status_code",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.ENUM,
        options=[opt.value for opt in InverterStatusCodeOption],
        value_fn=get_inverter_status_message,
    ),
    FroniusSensorEntityDescription(
        key="led_state",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    FroniusSensorEntityDescription(
        key="led_color",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
]

LOGGER_ENTITY_DESCRIPTIONS: list[FroniusSensorEntityDescription] = [
    FroniusSensorEntityDescription(
        key="co2_factor",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FroniusSensorEntityDescription(
        key="cash_factor",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FroniusSensorEntityDescription(
        key="delivery_factor",
        state_class=SensorStateClass.MEASUREMENT,
    ),
]

METER_ENTITY_DESCRIPTIONS: list[FroniusSensorEntityDescription] = [
    FroniusSensorEntityDescription(
        key="current_ac_phase_1",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    FroniusSensorEntityDescription(
        key="current_ac_phase_2",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    FroniusSensorEntityDescription(
        key="current_ac_phase_3",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    FroniusSensorEntityDescription(
        key="energy_reactive_ac_consumed",
        native_unit_of_measurement=ENERGY_VOLT_AMPERE_REACTIVE_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
        invalid_when_falsy=True,
    ),
    FroniusSensorEntityDescription(
        key="energy_reactive_ac_produced",
        native_unit_of_measurement=ENERGY_VOLT_AMPERE_REACTIVE_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
        invalid_when_falsy=True,
    ),
    FroniusSensorEntityDescription(
        key="energy_real_ac_minus",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
        invalid_when_falsy=True,
    ),
    FroniusSensorEntityDescription(
        key="energy_real_ac_plus",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
        invalid_when_falsy=True,
    ),
    FroniusSensorEntityDescription(
        key="energy_real_consumed",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        invalid_when_falsy=True,
    ),
    FroniusSensorEntityDescription(
        key="energy_real_produced",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        invalid_when_falsy=True,
    ),
    FroniusSensorEntityDescription(
        key="frequency_phase_average",
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FroniusSensorEntityDescription(
        key="meter_location",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=int,  # type: ignore[arg-type]
    ),
    FroniusSensorEntityDescription(
        key="meter_location_description",
        response_key="meter_location",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.ENUM,
        options=[opt.value for opt in MeterLocationCodeOption],
        value_fn=get_meter_location_description,
    ),
    FroniusSensorEntityDescription(
        key="power_apparent_phase_1",
        native_unit_of_measurement=UnitOfApparentPower.VOLT_AMPERE,
        device_class=SensorDeviceClass.APPARENT_POWER,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    FroniusSensorEntityDescription(
        key="power_apparent_phase_2",
        native_unit_of_measurement=UnitOfApparentPower.VOLT_AMPERE,
        device_class=SensorDeviceClass.APPARENT_POWER,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    FroniusSensorEntityDescription(
        key="power_apparent_phase_3",
        native_unit_of_measurement=UnitOfApparentPower.VOLT_AMPERE,
        device_class=SensorDeviceClass.APPARENT_POWER,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    FroniusSensorEntityDescription(
        key="power_apparent",
        native_unit_of_measurement=UnitOfApparentPower.VOLT_AMPERE,
        device_class=SensorDeviceClass.APPARENT_POWER,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    FroniusSensorEntityDescription(
        key="power_factor_phase_1",
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    FroniusSensorEntityDescription(
        key="power_factor_phase_2",
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    FroniusSensorEntityDescription(
        key="power_factor_phase_3",
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    FroniusSensorEntityDescription(
        key="power_factor",
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FroniusSensorEntityDescription(
        key="power_reactive_phase_1",
        native_unit_of_measurement=POWER_VOLT_AMPERE_REACTIVE,
        device_class=SensorDeviceClass.REACTIVE_POWER,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    FroniusSensorEntityDescription(
        key="power_reactive_phase_2",
        native_unit_of_measurement=POWER_VOLT_AMPERE_REACTIVE,
        device_class=SensorDeviceClass.REACTIVE_POWER,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    FroniusSensorEntityDescription(
        key="power_reactive_phase_3",
        native_unit_of_measurement=POWER_VOLT_AMPERE_REACTIVE,
        device_class=SensorDeviceClass.REACTIVE_POWER,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    FroniusSensorEntityDescription(
        key="power_reactive",
        native_unit_of_measurement=POWER_VOLT_AMPERE_REACTIVE,
        device_class=SensorDeviceClass.REACTIVE_POWER,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    FroniusSensorEntityDescription(
        key="power_real_phase_1",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    FroniusSensorEntityDescription(
        key="power_real_phase_2",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    FroniusSensorEntityDescription(
        key="power_real_phase_3",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    FroniusSensorEntityDescription(
        key="power_real",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FroniusSensorEntityDescription(
        key="voltage_ac_phase_1",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    FroniusSensorEntityDescription(
        key="voltage_ac_phase_2",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    FroniusSensorEntityDescription(
        key="voltage_ac_phase_3",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    FroniusSensorEntityDescription(
        key="voltage_ac_phase_to_phase_12",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    FroniusSensorEntityDescription(
        key="voltage_ac_phase_to_phase_23",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    FroniusSensorEntityDescription(
        key="voltage_ac_phase_to_phase_31",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
]

OHMPILOT_ENTITY_DESCRIPTIONS: list[FroniusSensorEntityDescription] = [
    FroniusSensorEntityDescription(
        key="energy_real_ac_consumed",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        invalid_when_falsy=True,
    ),
    FroniusSensorEntityDescription(
        key="power_real_ac",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FroniusSensorEntityDescription(
        key="temperature_channel_1",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FroniusSensorEntityDescription(
        key="error_code",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    FroniusSensorEntityDescription(
        key="state_code",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    FroniusSensorEntityDescription(
        key="state_message",
        response_key="state_code",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.ENUM,
        options=[opt.value for opt in OhmPilotStateCodeOption],
        value_fn=get_ohmpilot_state_message,
    ),
]

POWER_FLOW_ENTITY_DESCRIPTIONS: list[FroniusSensorEntityDescription] = [
    FroniusSensorEntityDescription(
        key="energy_day",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
    ),
    FroniusSensorEntityDescription(
        key="energy_year",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
    ),
    FroniusSensorEntityDescription(
        key="energy_total",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        invalid_when_falsy=True,
        entity_registry_enabled_default=False,
    ),
    FroniusSensorEntityDescription(
        key="meter_mode",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    FroniusSensorEntityDescription(
        key="power_battery",
        default_value=0,
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    FroniusSensorEntityDescription(
        key="power_battery_discharge",
        response_key="power_battery",
        default_value=0,
        value_fn=lambda value: max(value, 0),  # type: ignore[type-var]
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FroniusSensorEntityDescription(
        key="power_battery_charge",
        response_key="power_battery",
        default_value=0,
        value_fn=lambda value: max(0 - value, 0),  # type: ignore[operator]
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FroniusSensorEntityDescription(
        key="power_grid",
        default_value=0,
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    FroniusSensorEntityDescription(
        key="power_grid_import",
        response_key="power_grid",
        default_value=0,
        value_fn=lambda value: max(value, 0),  # type: ignore[type-var]
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FroniusSensorEntityDescription(
        key="power_grid_export",
        response_key="power_grid",
        default_value=0,
        value_fn=lambda value: max(0 - value, 0),  # type: ignore[operator]
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FroniusSensorEntityDescription(
        key="power_load",
        default_value=0,
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    FroniusSensorEntityDescription(
        key="power_load_generated",
        response_key="power_load",
        default_value=0,
        value_fn=lambda value: max(value, 0),  # type: ignore[type-var]
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    FroniusSensorEntityDescription(
        key="power_load_consumed",
        response_key="power_load",
        default_value=0,
        value_fn=lambda value: max(0 - value, 0),  # type: ignore[operator]
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FroniusSensorEntityDescription(
        key="power_photovoltaics",
        default_value=0,
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FroniusSensorEntityDescription(
        key="relative_autonomy",
        default_value=0,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FroniusSensorEntityDescription(
        key="relative_self_consumption",
        default_value=0,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
]

STORAGE_ENTITY_DESCRIPTIONS: list[FroniusSensorEntityDescription] = [
    FroniusSensorEntityDescription(
        key="capacity_maximum",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    FroniusSensorEntityDescription(
        key="capacity_designed",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    FroniusSensorEntityDescription(
        key="current_dc",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FroniusSensorEntityDescription(
        key="voltage_dc",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FroniusSensorEntityDescription(
        key="voltage_dc_maximum_cell",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    FroniusSensorEntityDescription(
        key="voltage_dc_minimum_cell",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    FroniusSensorEntityDescription(
        key="state_of_charge",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FroniusSensorEntityDescription(
        key="temperature_cell",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
]


class _FroniusSensorEntity(CoordinatorEntity["FroniusCoordinatorBase"], SensorEntity):
    """Defines a Fronius coordinator entity."""

    entity_description: FroniusSensorEntityDescription

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: FroniusCoordinatorBase,
        description: FroniusSensorEntityDescription,
        solar_net_id: str,
    ) -> None:
        """Set up an individual Fronius meter sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self.response_key = description.response_key or description.key
        self.solar_net_id = solar_net_id
        self._attr_native_value = self._get_entity_value()
        self._attr_translation_key = description.key

    def _device_data(self) -> dict[str, Any]:
        """Extract information for SolarNet device from coordinator data."""
        return self.coordinator.data[self.solar_net_id]

    def _get_entity_value(self) -> Any:
        """Extract entity value from coordinator. Raises KeyError if not included in latest update."""
        new_value = self.coordinator.data[self.solar_net_id][self.response_key]["value"]
        if new_value is None:
            return self.entity_description.default_value
        if self.entity_description.invalid_when_falsy and not new_value:
            return None
        if self.entity_description.value_fn is not None:
            new_value = self.entity_description.value_fn(new_value)
        if isinstance(new_value, float):
            return round(new_value, 4)
        return new_value

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        try:
            self._attr_native_value = self._get_entity_value()
        except KeyError:
            # sets state to `None` if no default_value is defined in entity description
            # KeyError: raised when omitted in response - eg. at night when no production
            self._attr_native_value = self.entity_description.default_value
        self.async_write_ha_state()


class InverterSensor(_FroniusSensorEntity):
    """Defines a Fronius inverter device sensor entity."""

    def __init__(
        self,
        coordinator: FroniusInverterUpdateCoordinator,
        description: FroniusSensorEntityDescription,
        solar_net_id: str,
    ) -> None:
        """Set up an individual Fronius inverter sensor."""
        super().__init__(coordinator, description, solar_net_id)
        # device_info created in __init__ from a `GetInverterInfo` request
        self._attr_device_info = coordinator.inverter_info.device_info
        self._attr_unique_id = (
            f"{coordinator.inverter_info.unique_id}-{description.key}"
        )


class LoggerSensor(_FroniusSensorEntity):
    """Defines a Fronius logger device sensor entity."""

    def __init__(
        self,
        coordinator: FroniusLoggerUpdateCoordinator,
        description: FroniusSensorEntityDescription,
        solar_net_id: str,
    ) -> None:
        """Set up an individual Fronius meter sensor."""
        super().__init__(coordinator, description, solar_net_id)
        logger_data = self._device_data()
        # Logger device is already created in FroniusSolarNet._create_solar_net_device
        self._attr_device_info = coordinator.solar_net.system_device_info
        self._attr_native_unit_of_measurement = logger_data[self.response_key].get(
            "unit"
        )
        self._attr_unique_id = (
            f'{logger_data["unique_identifier"]["value"]}-{description.key}'
        )


class MeterSensor(_FroniusSensorEntity):
    """Defines a Fronius meter device sensor entity."""

    def __init__(
        self,
        coordinator: FroniusMeterUpdateCoordinator,
        description: FroniusSensorEntityDescription,
        solar_net_id: str,
    ) -> None:
        """Set up an individual Fronius meter sensor."""
        super().__init__(coordinator, description, solar_net_id)
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
        self._attr_unique_id = f"{meter_uid}-{description.key}"


class OhmpilotSensor(_FroniusSensorEntity):
    """Defines a Fronius Ohmpilot sensor entity."""

    def __init__(
        self,
        coordinator: FroniusOhmpilotUpdateCoordinator,
        description: FroniusSensorEntityDescription,
        solar_net_id: str,
    ) -> None:
        """Set up an individual Fronius meter sensor."""
        super().__init__(coordinator, description, solar_net_id)
        device_data = self._device_data()

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_data["serial"]["value"])},
            manufacturer=device_data["manufacturer"]["value"],
            model=f"{device_data['model']['value']} {device_data['hardware']['value']}",
            name=device_data["model"]["value"],
            sw_version=device_data["software"]["value"],
            via_device=(DOMAIN, coordinator.solar_net.solar_net_device_id),
        )
        self._attr_unique_id = f'{device_data["serial"]["value"]}-{description.key}'


class PowerFlowSensor(_FroniusSensorEntity):
    """Defines a Fronius power flow sensor entity."""

    def __init__(
        self,
        coordinator: FroniusPowerFlowUpdateCoordinator,
        description: FroniusSensorEntityDescription,
        solar_net_id: str,
    ) -> None:
        """Set up an individual Fronius power flow sensor."""
        super().__init__(coordinator, description, solar_net_id)
        # SolarNet device is already created in FroniusSolarNet._create_solar_net_device
        self._attr_device_info = coordinator.solar_net.system_device_info
        self._attr_unique_id = (
            f"{coordinator.solar_net.solar_net_device_id}-power_flow-{description.key}"
        )


class StorageSensor(_FroniusSensorEntity):
    """Defines a Fronius storage device sensor entity."""

    def __init__(
        self,
        coordinator: FroniusStorageUpdateCoordinator,
        description: FroniusSensorEntityDescription,
        solar_net_id: str,
    ) -> None:
        """Set up an individual Fronius storage sensor."""
        super().__init__(coordinator, description, solar_net_id)
        storage_data = self._device_data()

        self._attr_unique_id = f'{storage_data["serial"]["value"]}-{description.key}'
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, storage_data["serial"]["value"])},
            manufacturer=storage_data["manufacturer"]["value"],
            model=storage_data["model"]["value"],
            name=storage_data["model"]["value"],
            via_device=(DOMAIN, coordinator.solar_net.solar_net_device_id),
        )
