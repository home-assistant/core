"""Support for Fronius devices."""

from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import TYPE_CHECKING, Any, Final, cast, override

from fronius_solarapi import (
    CommonInverterData,
    DeviceDetails,
    DeviceStatus,
    InverterState,
    LoggerInfo,
    MeterData,
    MeterLocation,
    OhmpilotData,
    OhmpilotState,
    PowerFlow,
    StorageController,
)

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
    UnitOfReactiveEnergy,
    UnitOfReactivePower,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.device_registry import ChildDeviceInfo, DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import DOMAIN, INVERTER_ERROR_CODES, FroniusDeviceInfo, discovery_signal
from .coordinator import (
    FroniusCoordinatorBase,
    FroniusInverterUpdateCoordinator,
    FroniusLoggerUpdateCoordinator,
    FroniusMeterUpdateCoordinator,
    FroniusModbusInverterUpdateCoordinator,
    FroniusOhmpilotUpdateCoordinator,
    FroniusPowerFlowUpdateCoordinator,
    FroniusStorageUpdateCoordinator,
)
from .entity import (
    FroniusEntity,
    FroniusEntityDescription,
    ModbusValues,
    async_add_entities_for_seen_keys,
)

if TYPE_CHECKING:
    from . import FroniusConfigEntry

_LOGGER: Final = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


@callback
def _async_fix_modbus_sensor_unique_ids(
    hass: HomeAssistant, entry: FroniusConfigEntry
) -> None:
    """Move sensors that were registered with the SolarAPI unique ID format.

    A Modbus coordinator found by a re-scan reached the sensor platform
    before it could be told from a SolarAPI one, so 2026.9 built its entities
    as SolarAPI ones: `<inverter>-<key>` instead of `<inverter>-modbus-<key>`.
    The keys of the two are distinct, so a Modbus key without the marker can
    only come from that.
    """
    modbus_keys = {
        description.key for description in MODBUS_INVERTER_ENTITY_DESCRIPTIONS
    }
    registry = er.async_get(hass)
    for entity in er.async_entries_for_config_entry(registry, entry.entry_id):
        inverter_id, _, key = entity.unique_id.rpartition("-")
        if key not in modbus_keys or inverter_id.endswith("-modbus"):
            continue
        unique_id = f"{inverter_id}-modbus-{key}"
        if registry.async_get_entity_id(entity.domain, DOMAIN, unique_id):
            continue
        _LOGGER.debug("Migrating unique ID of %s to %s", entity.entity_id, unique_id)
        registry.async_update_entity(entity.entity_id, new_unique_id=unique_id)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: FroniusConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Fronius sensor entities based on a config entry."""
    _async_fix_modbus_sensor_unique_ids(hass, config_entry)

    @callback
    def async_add_coordinator_entities(
        coordinator: FroniusCoordinatorBase[Any],
    ) -> None:
        """Add the sensors of a coordinator, also one found after setup."""
        match coordinator:
            case FroniusInverterUpdateCoordinator():
                async_add_entities_for_seen_keys(
                    coordinator,
                    INVERTER_ENTITY_DESCRIPTIONS,
                    InverterSensor,
                    async_add_entities,
                )
            case FroniusModbusInverterUpdateCoordinator():
                async_add_entities_for_seen_keys(
                    coordinator,
                    MODBUS_INVERTER_ENTITY_DESCRIPTIONS,
                    ModbusInverterSensor,
                    async_add_entities,
                )
            case FroniusLoggerUpdateCoordinator():
                async_add_entities_for_seen_keys(
                    coordinator,
                    LOGGER_ENTITY_DESCRIPTIONS,
                    LoggerSensor,
                    async_add_entities,
                )
            case FroniusMeterUpdateCoordinator():
                async_add_entities_for_seen_keys(
                    coordinator,
                    METER_ENTITY_DESCRIPTIONS,
                    MeterSensor,
                    async_add_entities,
                )
            case FroniusOhmpilotUpdateCoordinator():
                async_add_entities_for_seen_keys(
                    coordinator,
                    OHMPILOT_ENTITY_DESCRIPTIONS,
                    OhmpilotSensor,
                    async_add_entities,
                )
            case FroniusPowerFlowUpdateCoordinator():
                async_add_entities_for_seen_keys(
                    coordinator,
                    POWER_FLOW_ENTITY_DESCRIPTIONS,
                    PowerFlowSensor,
                    async_add_entities,
                )
            case FroniusStorageUpdateCoordinator():
                async_add_entities_for_seen_keys(
                    coordinator,
                    STORAGE_ENTITY_DESCRIPTIONS,
                    StorageSensor,
                    async_add_entities,
                )

    for coordinator in config_entry.runtime_data.coordinators:
        async_add_coordinator_entities(coordinator)
    config_entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            discovery_signal(config_entry.entry_id),
            async_add_coordinator_entities,
        )
    )


@dataclass(frozen=True, kw_only=True)
class FroniusSensorEntityDescription[_DataT](
    FroniusEntityDescription[_DataT], SensorEntityDescription
):
    """Describes Fronius sensor entity."""

    value_fn: Callable[[_DataT], StateType]
    default_value: StateType | None = None
    # Gen24 devices may report 0 for total energy while doing firmware updates.
    # Handling such values shall mitigate spikes in delta calculations.
    invalid_when_falsy: bool = False
    # the unit where the device reports it along with the value
    unit_fn: Callable[[_DataT], str | None] | None = None
    # set for readings of a single MPPT module, which get their own child device
    mppt_no: int | None = None


_NO_DEVICE_STATUS: Final = DeviceStatus(
    status_code=None,
    error_code=None,
    led_color=None,
    led_state=None,
    mgmt_timer_remaining_time=None,
    state_to_reset=None,
    inverter_state=None,
)


def _device_status(data: CommonInverterData) -> DeviceStatus:
    """Return the status of an inverter, empty when it reported none."""
    return data.device_status or _NO_DEVICE_STATUS


def _inverter_state(data: CommonInverterData) -> InverterState | None:
    """Return the operational state of an inverter, `None` when unknown."""
    if (state := _device_status(data).state) is InverterState.UNKNOWN:
        return None
    return state


# the entity states and their translations use these, not the library's names
_METER_LOCATION_OPTIONS: Final[dict[MeterLocation, str]] = {
    MeterLocation.GRID: "feed_in",
    MeterLocation.LOAD: "consumption_path",
    MeterLocation.EXTERNAL_GENERATOR: "external_generator",
    MeterLocation.EXTERNAL_GENERATOR_WITH_BATTERY: "external_battery",
    MeterLocation.SUBLOAD: "subload",
}
_OHMPILOT_STATE_OPTIONS: Final[dict[OhmpilotState, str]] = {
    OhmpilotState.UP_AND_RUNNING: "up_and_running",
    OhmpilotState.KEEP_MINIMUM_TEMPERATURE: "keep_minimum_temperature",
    OhmpilotState.LEGIONELLA_PROTECTION: "legionella_protection",
    OhmpilotState.CRITICAL_FAULT: "critical_fault",
    OhmpilotState.FAULT: "fault",
    OhmpilotState.BOOST_MODE: "boost_mode",
}


def _positive(value: float | None) -> float | None:
    """Return the positive part of a signed power."""
    return None if value is None else max(value, 0)


def _negative(value: float | None) -> float | None:
    """Return the negative part of a signed power, as a positive value."""
    return None if value is None else max(0 - value, 0)


def _modbus_value(key: str) -> Callable[[ModbusValues], StateType]:
    """Return a function reading a value of a Modbus coordinator."""
    return lambda values: values.get(key)


INVERTER_ENTITY_DESCRIPTIONS: list[
    FroniusSensorEntityDescription[CommonInverterData]
] = [
    FroniusSensorEntityDescription(
        key="energy_day",
        value_fn=lambda data: data.energy_day,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    FroniusSensorEntityDescription(
        key="energy_year",
        value_fn=lambda data: data.energy_year,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    FroniusSensorEntityDescription(
        key="energy_total",
        value_fn=lambda data: data.energy_total,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        invalid_when_falsy=True,
    ),
    FroniusSensorEntityDescription(
        key="frequency_ac",
        value_fn=lambda data: data.frequency_ac,
        default_value=0,
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    FroniusSensorEntityDescription(
        key="current_ac",
        value_fn=lambda data: data.current_ac,
        default_value=0,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FroniusSensorEntityDescription(
        key="current_dc",
        value_fn=lambda data: data.current_dc,
        default_value=0,
        mppt_no=1,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FroniusSensorEntityDescription(
        key="current_dc_2",
        value_fn=lambda data: data.current_dc_2,
        default_value=0,
        mppt_no=2,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        translation_key="current_dc",
    ),
    FroniusSensorEntityDescription(
        key="current_dc_3",
        value_fn=lambda data: data.current_dc_3,
        default_value=0,
        mppt_no=3,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        translation_key="current_dc",
    ),
    FroniusSensorEntityDescription(
        key="current_dc_4",
        value_fn=lambda data: data.current_dc_4,
        default_value=0,
        mppt_no=4,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        translation_key="current_dc",
    ),
    FroniusSensorEntityDescription(
        key="power_ac",
        value_fn=lambda data: data.power_ac,
        default_value=0,
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FroniusSensorEntityDescription(
        key="voltage_ac",
        value_fn=lambda data: data.voltage_ac,
        default_value=0,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    FroniusSensorEntityDescription(
        key="voltage_dc",
        value_fn=lambda data: data.voltage_dc,
        default_value=0,
        mppt_no=1,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FroniusSensorEntityDescription(
        key="voltage_dc_2",
        value_fn=lambda data: data.voltage_dc_2,
        default_value=0,
        mppt_no=2,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        translation_key="voltage_dc",
    ),
    FroniusSensorEntityDescription(
        key="voltage_dc_3",
        value_fn=lambda data: data.voltage_dc_3,
        default_value=0,
        mppt_no=3,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        translation_key="voltage_dc",
    ),
    FroniusSensorEntityDescription(
        key="voltage_dc_4",
        value_fn=lambda data: data.voltage_dc_4,
        default_value=0,
        mppt_no=4,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        translation_key="voltage_dc",
    ),
    # device status entities
    FroniusSensorEntityDescription(
        key="inverter_state",
        value_fn=lambda data: _device_status(data).inverter_state,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    FroniusSensorEntityDescription(
        key="error_code",
        value_fn=lambda data: _device_status(data).error_code,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    FroniusSensorEntityDescription(
        key="error_message",
        value_fn=lambda data: (
            None
            if (code := _device_status(data).error_code) is None
            else INVERTER_ERROR_CODES.get(code)
        ),
        exists_fn=lambda data: _device_status(data).error_code is not None,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.ENUM,
        options=list(dict.fromkeys(INVERTER_ERROR_CODES.values())),
    ),
    FroniusSensorEntityDescription(
        key="status_code",
        value_fn=lambda data: _device_status(data).status_code,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    FroniusSensorEntityDescription(
        key="status_message",
        value_fn=_inverter_state,
        exists_fn=lambda data: _device_status(data).status_code is not None,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.ENUM,
        options=[
            state.value for state in InverterState if state is not InverterState.UNKNOWN
        ],
    ),
    FroniusSensorEntityDescription(
        key="led_state",
        value_fn=lambda data: _device_status(data).led_state,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    FroniusSensorEntityDescription(
        key="led_color",
        value_fn=lambda data: _device_status(data).led_color,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
]


def _modbus_mppt_descriptions(
    mppt_no: int,
) -> list[FroniusSensorEntityDescription[ModbusValues]]:
    """Create entity descriptions for one MPPT module of SunSpec model 160."""
    return [
        FroniusSensorEntityDescription(
            key=f"mppt_{mppt_no}_current_dc",
            value_fn=_modbus_value(f"mppt_{mppt_no}_current_dc"),
            native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
            device_class=SensorDeviceClass.CURRENT,
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=False,
            translation_key="modbus_mppt_current_dc",
            mppt_no=mppt_no,
        ),
        FroniusSensorEntityDescription(
            key=f"mppt_{mppt_no}_voltage_dc",
            value_fn=_modbus_value(f"mppt_{mppt_no}_voltage_dc"),
            native_unit_of_measurement=UnitOfElectricPotential.VOLT,
            device_class=SensorDeviceClass.VOLTAGE,
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=False,
            translation_key="modbus_mppt_voltage_dc",
            mppt_no=mppt_no,
        ),
        FroniusSensorEntityDescription(
            key=f"mppt_{mppt_no}_power_dc",
            value_fn=_modbus_value(f"mppt_{mppt_no}_power_dc"),
            native_unit_of_measurement=UnitOfPower.WATT,
            device_class=SensorDeviceClass.POWER,
            state_class=SensorStateClass.MEASUREMENT,
            translation_key="modbus_mppt_power_dc",
            mppt_no=mppt_no,
        ),
        FroniusSensorEntityDescription(
            key=f"mppt_{mppt_no}_energy",
            value_fn=_modbus_value(f"mppt_{mppt_no}_energy"),
            native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
            device_class=SensorDeviceClass.ENERGY,
            state_class=SensorStateClass.TOTAL_INCREASING,
            invalid_when_falsy=True,
            mppt_no=mppt_no,
        ),
    ]


MODBUS_INVERTER_ENTITY_DESCRIPTIONS: list[
    FroniusSensorEntityDescription[ModbusValues]
] = [
    # Verto Plus exposes 5 modules (3 PV trackers plus storage charge/discharge),
    # one more leaves headroom for a hybrid with 4 PV trackers
    *(
        description
        for mppt_no in range(1, 7)
        for description in _modbus_mppt_descriptions(mppt_no)
    ),
    FroniusSensorEntityDescription(
        key="energy_total_pv",
        value_fn=_modbus_value("energy_total_pv"),
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        invalid_when_falsy=True,
    ),
    FroniusSensorEntityDescription(
        key="storage_energy_charged_total",
        value_fn=_modbus_value("storage_energy_charged_total"),
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        invalid_when_falsy=True,
    ),
    FroniusSensorEntityDescription(
        key="storage_energy_discharged_total",
        value_fn=_modbus_value("storage_energy_discharged_total"),
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        invalid_when_falsy=True,
    ),
]

LOGGER_ENTITY_DESCRIPTIONS: list[FroniusSensorEntityDescription[LoggerInfo]] = [
    FroniusSensorEntityDescription(
        key="co2_factor",
        value_fn=lambda data: data.co2_factor if data.co2_unit is not None else None,
        unit_fn=lambda data: f"{data.co2_unit}/kWh",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FroniusSensorEntityDescription(
        key="cash_factor",
        value_fn=lambda data: (
            data.cash_factor if data.cash_currency is not None else None
        ),
        unit_fn=lambda data: f"{data.cash_currency}/kWh",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FroniusSensorEntityDescription(
        key="delivery_factor",
        value_fn=lambda data: (
            data.delivery_factor if data.cash_currency is not None else None
        ),
        unit_fn=lambda data: f"{data.cash_currency}/kWh",
        state_class=SensorStateClass.MEASUREMENT,
    ),
]

METER_ENTITY_DESCRIPTIONS: list[FroniusSensorEntityDescription[MeterData]] = [
    FroniusSensorEntityDescription(
        key="current_ac_phase_1",
        value_fn=lambda data: data.current_ac_phase_1,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    FroniusSensorEntityDescription(
        key="current_ac_phase_2",
        value_fn=lambda data: data.current_ac_phase_2,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    FroniusSensorEntityDescription(
        key="current_ac_phase_3",
        value_fn=lambda data: data.current_ac_phase_3,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    FroniusSensorEntityDescription(
        key="energy_reactive_ac_consumed",
        value_fn=lambda data: data.energy_reactive_consumed,
        native_unit_of_measurement=UnitOfReactiveEnergy.VOLT_AMPERE_REACTIVE_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
        invalid_when_falsy=True,
    ),
    FroniusSensorEntityDescription(
        key="energy_reactive_ac_produced",
        value_fn=lambda data: data.energy_reactive_produced,
        native_unit_of_measurement=UnitOfReactiveEnergy.VOLT_AMPERE_REACTIVE_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
        invalid_when_falsy=True,
    ),
    FroniusSensorEntityDescription(
        key="energy_real_ac_minus",
        value_fn=lambda data: data.energy_real_minus_absolute,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
        invalid_when_falsy=True,
    ),
    FroniusSensorEntityDescription(
        key="energy_real_ac_plus",
        value_fn=lambda data: data.energy_real_plus_absolute,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
        invalid_when_falsy=True,
    ),
    FroniusSensorEntityDescription(
        key="energy_real_consumed",
        value_fn=lambda data: data.energy_real_consumed,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        invalid_when_falsy=True,
    ),
    FroniusSensorEntityDescription(
        key="energy_real_produced",
        value_fn=lambda data: data.energy_real_produced,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        invalid_when_falsy=True,
    ),
    FroniusSensorEntityDescription(
        key="frequency_phase_average",
        value_fn=lambda data: data.frequency_phase_average,
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FroniusSensorEntityDescription(
        key="meter_location",
        value_fn=lambda data: data.meter_location_code,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    FroniusSensorEntityDescription(
        key="meter_location_description",
        value_fn=lambda data: (
            None
            if (location := data.meter_location) is None
            else _METER_LOCATION_OPTIONS[location]
        ),
        exists_fn=lambda data: data.meter_location_code is not None,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.ENUM,
        options=list(_METER_LOCATION_OPTIONS.values()),
    ),
    FroniusSensorEntityDescription(
        key="power_apparent_phase_1",
        value_fn=lambda data: data.power_apparent_phase_1,
        native_unit_of_measurement=UnitOfApparentPower.VOLT_AMPERE,
        device_class=SensorDeviceClass.APPARENT_POWER,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    FroniusSensorEntityDescription(
        key="power_apparent_phase_2",
        value_fn=lambda data: data.power_apparent_phase_2,
        native_unit_of_measurement=UnitOfApparentPower.VOLT_AMPERE,
        device_class=SensorDeviceClass.APPARENT_POWER,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    FroniusSensorEntityDescription(
        key="power_apparent_phase_3",
        value_fn=lambda data: data.power_apparent_phase_3,
        native_unit_of_measurement=UnitOfApparentPower.VOLT_AMPERE,
        device_class=SensorDeviceClass.APPARENT_POWER,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    FroniusSensorEntityDescription(
        key="power_apparent",
        value_fn=lambda data: data.power_apparent,
        native_unit_of_measurement=UnitOfApparentPower.VOLT_AMPERE,
        device_class=SensorDeviceClass.APPARENT_POWER,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    FroniusSensorEntityDescription(
        key="power_factor_phase_1",
        value_fn=lambda data: data.power_factor_phase_1,
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    FroniusSensorEntityDescription(
        key="power_factor_phase_2",
        value_fn=lambda data: data.power_factor_phase_2,
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    FroniusSensorEntityDescription(
        key="power_factor_phase_3",
        value_fn=lambda data: data.power_factor_phase_3,
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    FroniusSensorEntityDescription(
        key="power_factor",
        value_fn=lambda data: data.power_factor,
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FroniusSensorEntityDescription(
        key="power_reactive_phase_1",
        value_fn=lambda data: data.power_reactive_phase_1,
        native_unit_of_measurement=UnitOfReactivePower.VOLT_AMPERE_REACTIVE,
        device_class=SensorDeviceClass.REACTIVE_POWER,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    FroniusSensorEntityDescription(
        key="power_reactive_phase_2",
        value_fn=lambda data: data.power_reactive_phase_2,
        native_unit_of_measurement=UnitOfReactivePower.VOLT_AMPERE_REACTIVE,
        device_class=SensorDeviceClass.REACTIVE_POWER,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    FroniusSensorEntityDescription(
        key="power_reactive_phase_3",
        value_fn=lambda data: data.power_reactive_phase_3,
        native_unit_of_measurement=UnitOfReactivePower.VOLT_AMPERE_REACTIVE,
        device_class=SensorDeviceClass.REACTIVE_POWER,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    FroniusSensorEntityDescription(
        key="power_reactive",
        value_fn=lambda data: data.power_reactive,
        native_unit_of_measurement=UnitOfReactivePower.VOLT_AMPERE_REACTIVE,
        device_class=SensorDeviceClass.REACTIVE_POWER,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    FroniusSensorEntityDescription(
        key="power_real_phase_1",
        value_fn=lambda data: data.power_real_phase_1,
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    FroniusSensorEntityDescription(
        key="power_real_phase_2",
        value_fn=lambda data: data.power_real_phase_2,
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    FroniusSensorEntityDescription(
        key="power_real_phase_3",
        value_fn=lambda data: data.power_real_phase_3,
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    FroniusSensorEntityDescription(
        key="power_real",
        value_fn=lambda data: data.power_real,
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FroniusSensorEntityDescription(
        key="voltage_ac_phase_1",
        value_fn=lambda data: data.voltage_ac_phase_1,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    FroniusSensorEntityDescription(
        key="voltage_ac_phase_2",
        value_fn=lambda data: data.voltage_ac_phase_2,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    FroniusSensorEntityDescription(
        key="voltage_ac_phase_3",
        value_fn=lambda data: data.voltage_ac_phase_3,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    FroniusSensorEntityDescription(
        key="voltage_ac_phase_to_phase_12",
        value_fn=lambda data: data.voltage_ac_phase_to_phase_12,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    FroniusSensorEntityDescription(
        key="voltage_ac_phase_to_phase_23",
        value_fn=lambda data: data.voltage_ac_phase_to_phase_23,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    FroniusSensorEntityDescription(
        key="voltage_ac_phase_to_phase_31",
        value_fn=lambda data: data.voltage_ac_phase_to_phase_31,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
]

OHMPILOT_ENTITY_DESCRIPTIONS: list[FroniusSensorEntityDescription[OhmpilotData]] = [
    FroniusSensorEntityDescription(
        key="energy_real_ac_consumed",
        value_fn=lambda data: data.energy_real_consumed,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        invalid_when_falsy=True,
    ),
    FroniusSensorEntityDescription(
        key="power_real_ac",
        value_fn=lambda data: data.power_real,
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FroniusSensorEntityDescription(
        key="temperature_channel_1",
        value_fn=lambda data: data.temperature_channel_1,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FroniusSensorEntityDescription(
        key="error_code",
        value_fn=lambda data: data.error_code,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    FroniusSensorEntityDescription(
        key="state_code",
        value_fn=lambda data: data.state_code,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    FroniusSensorEntityDescription(
        key="state_message",
        value_fn=lambda data: (
            None if (state := data.state) is None else _OHMPILOT_STATE_OPTIONS[state]
        ),
        exists_fn=lambda data: data.state_code is not None,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.ENUM,
        options=list(_OHMPILOT_STATE_OPTIONS.values()),
    ),
]

POWER_FLOW_ENTITY_DESCRIPTIONS: list[FroniusSensorEntityDescription[PowerFlow]] = [
    FroniusSensorEntityDescription(
        key="energy_day",
        value_fn=lambda data: data.site.energy_day,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
    ),
    FroniusSensorEntityDescription(
        key="energy_year",
        value_fn=lambda data: data.site.energy_year,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
    ),
    FroniusSensorEntityDescription(
        key="energy_total",
        value_fn=lambda data: data.site.energy_total,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        invalid_when_falsy=True,
        entity_registry_enabled_default=False,
    ),
    FroniusSensorEntityDescription(
        key="meter_mode",
        value_fn=lambda data: data.site.mode,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    FroniusSensorEntityDescription(
        key="power_battery",
        value_fn=lambda data: data.site.power_battery,
        default_value=0,
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    FroniusSensorEntityDescription(
        key="power_battery_discharge",
        value_fn=lambda data: _positive(data.site.power_battery),
        default_value=0,
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FroniusSensorEntityDescription(
        key="power_battery_charge",
        value_fn=lambda data: _negative(data.site.power_battery),
        default_value=0,
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FroniusSensorEntityDescription(
        key="power_grid",
        value_fn=lambda data: data.site.power_grid,
        default_value=0,
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    FroniusSensorEntityDescription(
        key="power_grid_import",
        value_fn=lambda data: _positive(data.site.power_grid),
        default_value=0,
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FroniusSensorEntityDescription(
        key="power_grid_export",
        value_fn=lambda data: _negative(data.site.power_grid),
        default_value=0,
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FroniusSensorEntityDescription(
        key="power_load",
        value_fn=lambda data: data.site.power_load,
        default_value=0,
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    FroniusSensorEntityDescription(
        key="power_load_generated",
        value_fn=lambda data: _positive(data.site.power_load),
        default_value=0,
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    FroniusSensorEntityDescription(
        key="power_load_consumed",
        value_fn=lambda data: _negative(data.site.power_load),
        default_value=0,
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FroniusSensorEntityDescription(
        key="power_photovoltaics",
        value_fn=lambda data: data.site.power_photovoltaics,
        default_value=0,
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FroniusSensorEntityDescription(
        key="relative_autonomy",
        value_fn=lambda data: data.site.relative_autonomy,
        default_value=0,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FroniusSensorEntityDescription(
        key="relative_self_consumption",
        value_fn=lambda data: data.site.relative_self_consumption,
        default_value=0,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
]

STORAGE_ENTITY_DESCRIPTIONS: list[FroniusSensorEntityDescription[StorageController]] = [
    FroniusSensorEntityDescription(
        key="capacity_maximum",
        value_fn=lambda data: data.capacity_maximum,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    FroniusSensorEntityDescription(
        key="capacity_designed",
        value_fn=lambda data: data.designed_capacity,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    FroniusSensorEntityDescription(
        key="current_dc",
        value_fn=lambda data: data.current_dc,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FroniusSensorEntityDescription(
        key="voltage_dc",
        value_fn=lambda data: data.voltage_dc,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FroniusSensorEntityDescription(
        key="voltage_dc_maximum_cell",
        value_fn=lambda data: data.voltage_dc_maximum_cell,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    FroniusSensorEntityDescription(
        key="voltage_dc_minimum_cell",
        value_fn=lambda data: data.voltage_dc_minimum_cell,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    FroniusSensorEntityDescription(
        key="state_of_charge",
        value_fn=lambda data: data.state_of_charge,
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FroniusSensorEntityDescription(
        key="temperature_cell",
        value_fn=lambda data: data.temperature_cell,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
]


def _inverter_device_info(
    inverter_info: FroniusDeviceInfo, mppt_no: int | None
) -> DeviceInfo | ChildDeviceInfo:
    """Return the inverter device, or the child device of one of its MPPT modules."""
    if mppt_no is None:
        return inverter_info.device_info
    return ChildDeviceInfo(
        identifiers={(DOMAIN, f"{inverter_info.unique_id}-mppt-{mppt_no}")},
        parent_device_id=inverter_info.device_id,
        translation_key="mppt",
        translation_placeholders={"mppt_no": str(mppt_no)},
    )


class _FroniusSensorEntity(FroniusEntity, SensorEntity):
    """Defines a Fronius coordinator sensor entity."""

    entity_description: FroniusSensorEntityDescription[Any]

    def __init__(
        self,
        coordinator: FroniusCoordinatorBase[Any],
        description: FroniusSensorEntityDescription[Any],
        solar_net_id: str,
    ) -> None:
        """Set up an individual Fronius sensor."""
        super().__init__(coordinator, description, solar_net_id)
        self._attr_native_value = self._get_entity_value()

    def _get_entity_value(self) -> StateType:
        """Extract entity value from coordinator.

        Raises KeyError if the device was not included in latest update.
        """
        new_value: StateType = self._value()
        if new_value is None:
            return self.entity_description.default_value
        if self.entity_description.invalid_when_falsy and not new_value:
            return None
        if isinstance(new_value, float):
            return round(new_value, 4)
        return new_value

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        try:
            self._attr_native_value = self._get_entity_value()
        except KeyError:
            # the device is missing from the latest update, e.g. a meter
            # that went offline - sets state to `None` if no default_value
            # is defined in entity description
            self._attr_native_value = self.entity_description.default_value
        self.async_write_ha_state()


def _child_device_info(
    coordinator: FroniusCoordinatorBase[Any],
    identifier: str,
    details: DeviceDetails,
    model: str | None = None,
) -> DeviceInfo:
    """Return the info of a device connected to the SolarNet logging device."""
    return DeviceInfo(
        identifiers={(DOMAIN, identifier)},
        manufacturer=details.manufacturer,
        model=model if model is not None else details.model,
        name=details.model,
        sw_version=details.software,
        via_device_id=dr.async_get_device_id_by_identifier(
            coordinator.hass,
            (DOMAIN, coordinator.solar_net.solar_net_device_id),
            config_entry_id=coordinator.config_entry.entry_id,
        ),
    )


class InverterSensor(_FroniusSensorEntity):
    """Defines a Fronius inverter device sensor entity."""

    def __init__(
        self,
        coordinator: FroniusInverterUpdateCoordinator,
        description: FroniusSensorEntityDescription[CommonInverterData],
        solar_net_id: str,
    ) -> None:
        """Set up an individual Fronius inverter sensor."""
        super().__init__(coordinator, description, solar_net_id)
        self._attr_device_info = _inverter_device_info(
            coordinator.inverter_info, description.mppt_no
        )
        self._attr_unique_id = (
            f"{coordinator.inverter_info.unique_id}-{description.key}"
        )


class ModbusInverterSensor(_FroniusSensorEntity):
    """Defines a Fronius Modbus inverter device sensor entity."""

    def __init__(
        self,
        coordinator: FroniusModbusInverterUpdateCoordinator,
        description: FroniusSensorEntityDescription[ModbusValues],
        solar_net_id: str,
    ) -> None:
        """Set up an individual Fronius Modbus inverter sensor."""
        super().__init__(coordinator, description, solar_net_id)
        # attach to the same devices as the SolarAPI inverter sensors
        self._attr_device_info = _inverter_device_info(
            coordinator.inverter_info, description.mppt_no
        )
        self._attr_unique_id = (
            f"{coordinator.inverter_info.unique_id}-modbus-{description.key}"
        )


class LoggerSensor(_FroniusSensorEntity):
    """Defines a Fronius logger device sensor entity."""

    def __init__(
        self,
        coordinator: FroniusLoggerUpdateCoordinator,
        description: FroniusSensorEntityDescription[LoggerInfo],
        solar_net_id: str,
    ) -> None:
        """Set up an individual Fronius logger sensor."""
        super().__init__(coordinator, description, solar_net_id)
        logger_info: LoggerInfo = self._device_data()
        # Logger device is already created in FroniusSolarNet._create_solar_net_device
        self._attr_device_info = coordinator.solar_net.system_device_info
        if description.unit_fn is not None:
            self._attr_native_unit_of_measurement = description.unit_fn(logger_info)
        self._attr_unique_id = f"{logger_info.unique_id}-{description.key}"


class MeterSensor(_FroniusSensorEntity):
    """Defines a Fronius meter device sensor entity."""

    def __init__(
        self,
        coordinator: FroniusMeterUpdateCoordinator,
        description: FroniusSensorEntityDescription[MeterData],
        solar_net_id: str,
    ) -> None:
        """Set up an individual Fronius meter sensor."""
        super().__init__(coordinator, description, solar_net_id)
        # the coordinator only adds entities for meters reporting a serial
        details = cast(DeviceDetails, cast(MeterData, self._device_data()).details)
        meter_uid = cast(str, details.serial)
        # S0 meters connected directly to inverters respond "n.a." as serial number
        # `model` contains the inverter id: "S0 Meter at inverter 1"
        if meter_uid == "n.a.":
            meter_uid = f"{coordinator.solar_net.solar_net_device_id}:{details.model}"
        self._attr_device_info = _child_device_info(coordinator, meter_uid, details)
        self._attr_unique_id = f"{meter_uid}-{description.key}"


class OhmpilotSensor(_FroniusSensorEntity):
    """Defines a Fronius Ohmpilot sensor entity."""

    def __init__(
        self,
        coordinator: FroniusOhmpilotUpdateCoordinator,
        description: FroniusSensorEntityDescription[OhmpilotData],
        solar_net_id: str,
    ) -> None:
        """Set up an individual Fronius Ohmpilot sensor."""
        super().__init__(coordinator, description, solar_net_id)
        # the coordinator only adds entities for Ohmpilots reporting a serial
        details = cast(DeviceDetails, cast(OhmpilotData, self._device_data()).details)
        serial = cast(str, details.serial)
        self._attr_device_info = _child_device_info(
            coordinator,
            serial,
            details,
            model=f"{details.model} {details.hardware}",
        )
        self._attr_unique_id = f"{serial}-{description.key}"


class PowerFlowSensor(_FroniusSensorEntity):
    """Defines a Fronius power flow sensor entity."""

    def __init__(
        self,
        coordinator: FroniusPowerFlowUpdateCoordinator,
        description: FroniusSensorEntityDescription[PowerFlow],
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
        description: FroniusSensorEntityDescription[StorageController],
        solar_net_id: str,
    ) -> None:
        """Set up an individual Fronius storage sensor."""
        super().__init__(coordinator, description, solar_net_id)
        # the coordinator only adds entities for storages reporting a serial
        details = cast(
            DeviceDetails, cast(StorageController, self._device_data()).details
        )
        serial = cast(str, details.serial)
        self._attr_unique_id = f"{serial}-{description.key}"
        self._attr_device_info = _child_device_info(coordinator, serial, details)
