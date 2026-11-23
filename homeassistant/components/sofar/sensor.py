"""Support for Sofar sensors."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import IntEnum
from typing import override

from sofar_modbus import (
    BATTERY_PACKS,
    BATTERY_STRING_COMPONENTS,
    PV_STRING_COMPONENTS,
    BatteryConfigCellType,
    BatteryConfigProtocol,
    BatteryPack,
    CorrectedTotal,
    FeedInLimitationMode,
    PassiveModeTimeoutAction,
    SofarInverter,
    SyncRtcResult,
    SystemState,
)

from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorExtraStoredData,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    Platform,
    UnitOfApparentPower,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfReactivePower,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import DOMAIN
from .coordinator import SofarConfigEntry, SofarRuntimeData
from .entity import (
    SofarEntity,
    SofarEntityDescription,
    SofarPart,
    async_remove_unserved_entities,
    battery_pack_identifier,
)
from .helpers import enum_options, option_slug

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SofarConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Sofar sensor platform."""
    async_remove_unserved_entities(
        hass,
        entry,
        Platform.SENSOR,
        SENSOR_DESCRIPTIONS + ENUM_SENSOR_DESCRIPTIONS + TOTAL_SENSOR_DESCRIPTIONS,
    )
    runtime_data = entry.runtime_data

    entities: list[SofarSensor | SofarEnumSensor | SofarTotalSensor] = [
        SofarSensor(runtime_data, description)
        for description in SENSOR_DESCRIPTIONS
        if description.component in runtime_data.served_components
        and _battery_string(description) is None
    ]
    entities.extend(
        SofarEnumSensor(runtime_data, description)
        for description in ENUM_SENSOR_DESCRIPTIONS
        if description.component in runtime_data.served_components
    )
    entities.extend(
        SofarTotalSensor(runtime_data, description)
        for description in TOTAL_SENSOR_DESCRIPTIONS
        if description.component in runtime_data.served_components
    )
    async_add_entities(entities)

    @callback
    def _async_add_wired_battery_strings() -> None:
        """Add a battery string's sensors the first time it reports a voltage."""
        new = (
            runtime_data.readings.device.wired_battery_strings
            - runtime_data.added_battery_strings
        )
        if not new:
            return
        runtime_data.added_battery_strings.update(new)
        async_add_entities(
            SofarSensor(runtime_data, description)
            for description in SENSOR_DESCRIPTIONS
            if _battery_string(description) in new
        )

    _async_add_wired_battery_strings()
    entry.async_on_unload(
        runtime_data.readings.async_add_listener(_async_add_wired_battery_strings)
    )
    if BATTERY_PACKS in runtime_data.served_components:
        _async_setup_battery_packs(entry, runtime_data, async_add_entities)


@callback
def _async_setup_battery_packs(
    entry: SofarConfigEntry,
    runtime_data: SofarRuntimeData,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add each BTS pack's sensors the first time the pack answers."""

    @callback
    def _async_add_answered_packs() -> None:
        """Add the sensors of packs that answered for the first time."""
        new = {
            place: pack
            for place, pack in runtime_data.readings.device.battery_packs.items()
            if pack.answered and place not in runtime_data.added_battery_packs
        }
        if not new:
            return
        runtime_data.added_battery_packs.update(new)
        async_add_entities(
            SofarPackSensor(runtime_data, description, pack)
            for pack in new.values()
            for description in PACK_SENSOR_DESCRIPTIONS
            if description.exists_fn(pack)
        )

    _async_add_answered_packs()
    entry.async_on_unload(
        runtime_data.packs.async_add_listener(_async_add_answered_packs)
    )


def _battery_string(description: SofarSensorDescription) -> int | None:
    """Return the battery string a description belongs to, if any."""
    if (part := description.part) is None or part.kind != "battery":
        return None
    return part.number


class SofarSensor(SofarEntity, SensorEntity):
    """Defines a Sofar sensor."""

    entity_description: SofarSensorDescription

    @property
    @override
    def native_value(self) -> StateType:
        return self.entity_description.value_fn(self.coordinator.device)


class SofarEnumSensor(SofarEntity, SensorEntity):
    """Defines a Sofar enum sensor."""

    entity_description: SofarEnumSensorDescription

    @property
    @override
    def native_value(self) -> str | None:
        # IntEnum stringifies as the raw int; use the option slug.
        value = self.entity_description.value_fn(self.coordinator.device)
        return option_slug(value) if value is not None else None


def restored_total(data: SensorExtraStoredData | None) -> float | None:
    """Return a stored total, if the stored state holds a number."""
    if data is None or not isinstance(data.native_value, (int, float)):
        return None
    return data.native_value


class SofarTotalSensor(SofarEntity, RestoreSensor):
    """Defines a Sofar cumulative total sensor."""

    entity_description: SofarTotalSensorDescription

    @override
    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if (
            total := restored_total(await self.async_get_last_sensor_data())
        ) is not None:
            self._attr_native_value = total
        self._take_total()

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        self._take_total()
        super()._handle_coordinator_update()

    def _take_total(self) -> None:
        """Keep the last total while the inverter reports none."""
        if (
            value := self.entity_description.total_fn(self.coordinator.device).value
        ) is not None:
            self._attr_native_value = value


class SofarPackSensor(SofarEntity, SensorEntity):
    """Defines a Sofar BTS battery pack sensor."""

    entity_description: SofarPackSensorDescription

    def __init__(
        self,
        runtime_data: SofarRuntimeData,
        entity_description: SofarPackSensorDescription,
        pack: BatteryPack,
    ) -> None:
        """Initialize the entity."""
        super().__init__(runtime_data, entity_description)
        self._pack = pack
        identifier = battery_pack_identifier(
            self.coordinator.device.serial_number, pack
        )
        # Every pack repeats the same keys.
        self._attr_unique_id = f"{identifier}_{entity_description.key}"
        self._attr_device_info = dr.DeviceInfo(
            identifiers={(DOMAIN, identifier)},
            via_device_id=runtime_data.inverter_device_id,
            translation_key="battery_pack",
            translation_placeholders={
                "group": str(pack.group_nr + 1),
                "pack": str(pack.pack_nr + 1),
            },
            model=pack.pack_model or None,
            sw_version=None if pack.bms_version is None else str(pack.bms_version),
            serial_number=pack.pack_serial_number or None,
        )

    @property
    @override
    def available(self) -> bool:
        """Whether this pack answered the most recent pack poll."""
        return super().available and self._pack.answered

    @property
    @override
    def native_value(self) -> StateType:
        return self.entity_description.value_fn(self._pack)


@dataclass(frozen=True, kw_only=True)
class SofarSensorDescription(SensorEntityDescription, SofarEntityDescription):
    """Describe a Sofar sensor."""

    value_fn: Callable[[SofarInverter], StateType]


@dataclass(frozen=True, kw_only=True)
class SofarEnumSensorDescription(SensorEntityDescription, SofarEntityDescription):
    """Describe a Sofar enum sensor."""

    value_fn: Callable[[SofarInverter], IntEnum | None]


@dataclass(frozen=True, kw_only=True)
class SofarTotalSensorDescription(SensorEntityDescription, SofarEntityDescription):
    """Describe a Sofar cumulative total sensor."""

    total_fn: Callable[[SofarInverter], CorrectedTotal]


@dataclass(frozen=True, kw_only=True)
class SofarPackSensorDescription(SensorEntityDescription, SofarEntityDescription):
    """Describe a Sofar BTS battery pack sensor."""

    exists_fn: Callable[[BatteryPack], bool] = lambda _: True
    value_fn: Callable[[BatteryPack], StateType]


@dataclass(frozen=True, kw_only=True)
class _PartMeasurement:
    """One measurement every string repeats, before it gets a number."""

    key: str
    translation_key: str
    device_class: SensorDeviceClass | None = None
    native_unit_of_measurement: str | None = None
    state_class: SensorStateClass | None = None
    suggested_display_precision: int | None = None
    entity_category: EntityCategory | None = None
    entity_registry_enabled_default: bool = True
    value_fn: Callable[[SofarInverter, int], StateType]


_PV_STRING_MEASUREMENTS = (
    _PartMeasurement(
        key="pv_voltage",
        translation_key="voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        entity_registry_enabled_default=False,
        value_fn=lambda device, number: device.pv_string(number).voltage,
    ),
    _PartMeasurement(
        key="pv_current",
        translation_key="current",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
        value_fn=lambda device, number: device.pv_string(number).current,
    ),
    _PartMeasurement(
        key="pv_power",
        translation_key="power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda device, number: device.pv_string(number).power,
    ),
)

_BATTERY_MEASUREMENTS = (
    _PartMeasurement(
        key="battery_voltage",
        translation_key="voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        value_fn=lambda device, number: device.battery_string(number).voltage,
    ),
    _PartMeasurement(
        key="battery_current",
        translation_key="current",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        suggested_display_precision=2,
        value_fn=lambda device, number: device.battery_string(number).current,
    ),
    _PartMeasurement(
        key="battery_power",
        translation_key="power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda device, number: device.battery_string(number).power,
    ),
    _PartMeasurement(
        key="battery_temperature",
        translation_key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda device, number: device.battery_string(number).temperature,
    ),
    _PartMeasurement(
        key="battery_capacity",
        translation_key="state_of_charge",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda device, number: device.battery_string(number).capacity,
    ),
    _PartMeasurement(
        key="battery_state_of_health",
        translation_key="state_of_health",
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda device, number: device.battery_string(number).state_of_health,
    ),
    _PartMeasurement(
        key="battery_charge_cycle",
        translation_key="charge_cycle",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda device, number: device.battery_string(number).charge_cycle,
    ),
)


def _part_sensors(
    kind: str,
    components: Mapping[int, str],
    measurements: tuple[_PartMeasurement, ...],
) -> tuple[SofarSensorDescription, ...]:
    """Repeat a part's measurements across every string it has."""
    return tuple(
        SofarSensorDescription(
            key=f"{measurement.key}_{number}",
            component=component,
            translation_key=measurement.translation_key,
            part=SofarPart(kind, number),
            device_class=measurement.device_class,
            native_unit_of_measurement=measurement.native_unit_of_measurement,
            state_class=measurement.state_class,
            suggested_display_precision=measurement.suggested_display_precision,
            entity_category=measurement.entity_category,
            entity_registry_enabled_default=(
                measurement.entity_registry_enabled_default
            ),
            value_fn=_part_value_fn(measurement.value_fn, number),
        )
        for number, component in components.items()
        for measurement in measurements
    )


def _part_value_fn(
    value_fn: Callable[[SofarInverter, int], StateType], number: int
) -> Callable[[SofarInverter], StateType]:
    """Bind a measurement to one numbered string."""
    return lambda device: value_fn(device, number)


SENSOR_DESCRIPTIONS: tuple[SofarSensorDescription, ...] = (
    SofarSensorDescription(
        key="pv_power_total",
        component="pv_1_2",
        translation_key="pv_power_total",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda device: device.pv_1_2.pv_power_total,
    ),
    SofarSensorDescription(
        key="inverter_temperature_1",
        component="state",
        translation_key="inverter_temperature_1",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda device: device.state.inverter_temperature_1,
    ),
    SofarSensorDescription(
        key="inverter_temperature_2",
        component="state",
        translation_key="inverter_temperature_2",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda device: device.state.inverter_temperature_2,
    ),
    SofarSensorDescription(
        key="heatsink_temperature_1",
        component="state",
        translation_key="heatsink_temperature_1",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda device: device.state.heatsink_temperature_1,
    ),
    SofarSensorDescription(
        key="heatsink_temperature_2",
        component="state",
        translation_key="heatsink_temperature_2",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda device: device.state.heatsink_temperature_2,
    ),
    SofarSensorDescription(
        key="module_temperature_1",
        component="state",
        translation_key="module_temperature_1",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda device: device.state.module_temperature_1,
    ),
    SofarSensorDescription(
        key="module_temperature_2",
        component="state",
        translation_key="module_temperature_2",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda device: device.state.module_temperature_2,
    ),
    SofarSensorDescription(
        key="grid_frequency",
        component="grid",
        translation_key="grid_frequency",
        device_class=SensorDeviceClass.FREQUENCY,
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        suggested_display_precision=2,
        value_fn=lambda device: device.grid.grid_frequency,
    ),
    SofarSensorDescription(
        key="active_power_output_total",
        component="grid",
        translation_key="active_power_output_total",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda device: device.grid.active_power_output_total,
    ),
    SofarSensorDescription(
        key="reactive_power_output_total",
        component="grid",
        translation_key="reactive_power_output_total",
        device_class=SensorDeviceClass.REACTIVE_POWER,
        native_unit_of_measurement=UnitOfReactivePower.KILO_VOLT_AMPERE_REACTIVE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        suggested_display_precision=2,
        value_fn=lambda device: device.grid.reactive_power_output_total,
    ),
    SofarSensorDescription(
        key="apparent_power_output_total",
        component="grid",
        translation_key="apparent_power_output_total",
        device_class=SensorDeviceClass.APPARENT_POWER,
        native_unit_of_measurement=UnitOfApparentPower.KILO_VOLT_AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda device: device.grid.apparent_power_output_total,
    ),
    SofarSensorDescription(
        key="active_power_pcc_total",
        component="grid",
        translation_key="active_power_pcc_total",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda device: device.grid.active_power_pcc_total,
    ),
    SofarSensorDescription(
        key="reactive_power_pcc_total",
        component="grid",
        translation_key="reactive_power_pcc_total",
        device_class=SensorDeviceClass.REACTIVE_POWER,
        native_unit_of_measurement=UnitOfReactivePower.KILO_VOLT_AMPERE_REACTIVE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        suggested_display_precision=2,
        value_fn=lambda device: device.grid.reactive_power_pcc_total,
    ),
    SofarSensorDescription(
        key="apparent_power_pcc_total",
        component="grid",
        translation_key="apparent_power_pcc_total",
        device_class=SensorDeviceClass.APPARENT_POWER,
        native_unit_of_measurement=UnitOfApparentPower.KILO_VOLT_AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda device: device.grid.apparent_power_pcc_total,
    ),
    SofarSensorDescription(
        key="voltage_l1",
        component="grid",
        translation_key="voltage_l1",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.grid.voltage_l1,
    ),
    SofarSensorDescription(
        key="current_output_l1",
        component="grid",
        translation_key="current_output_l1",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.grid.current_output_l1,
    ),
    SofarSensorDescription(
        key="active_power_output_l1",
        component="grid",
        translation_key="active_power_output_l1",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.grid.active_power_output_l1,
    ),
    SofarSensorDescription(
        key="reactive_power_output_l1",
        component="grid",
        translation_key="reactive_power_output_l1",
        device_class=SensorDeviceClass.REACTIVE_POWER,
        native_unit_of_measurement=UnitOfReactivePower.KILO_VOLT_AMPERE_REACTIVE,
        entity_registry_enabled_default=False,
        suggested_display_precision=2,
        value_fn=lambda device: device.grid.reactive_power_output_l1,
    ),
    SofarSensorDescription(
        key="power_factor_output_l1",
        component="grid",
        translation_key="power_factor_output_l1",
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.grid.power_factor_output_l1,
    ),
    SofarSensorDescription(
        key="current_pcc_l1",
        component="grid",
        translation_key="current_pcc_l1",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.grid.current_pcc_l1,
    ),
    SofarSensorDescription(
        key="active_power_pcc_l1",
        component="grid",
        translation_key="active_power_pcc_l1",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.grid.active_power_pcc_l1,
    ),
    SofarSensorDescription(
        key="reactive_power_pcc_l1",
        component="grid",
        translation_key="reactive_power_pcc_l1",
        device_class=SensorDeviceClass.REACTIVE_POWER,
        native_unit_of_measurement=UnitOfReactivePower.KILO_VOLT_AMPERE_REACTIVE,
        entity_registry_enabled_default=False,
        suggested_display_precision=2,
        value_fn=lambda device: device.grid.reactive_power_pcc_l1,
    ),
    SofarSensorDescription(
        key="power_factor_pcc_l1",
        component="grid",
        translation_key="power_factor_pcc_l1",
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.grid.power_factor_pcc_l1,
    ),
    SofarSensorDescription(
        key="voltage_l2",
        component="grid",
        translation_key="voltage_l2",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.grid.voltage_l2,
    ),
    SofarSensorDescription(
        key="current_output_l2",
        component="grid",
        translation_key="current_output_l2",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.grid.current_output_l2,
    ),
    SofarSensorDescription(
        key="active_power_output_l2",
        component="grid",
        translation_key="active_power_output_l2",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.grid.active_power_output_l2,
    ),
    SofarSensorDescription(
        key="reactive_power_output_l2",
        component="grid",
        translation_key="reactive_power_output_l2",
        device_class=SensorDeviceClass.REACTIVE_POWER,
        native_unit_of_measurement=UnitOfReactivePower.KILO_VOLT_AMPERE_REACTIVE,
        entity_registry_enabled_default=False,
        suggested_display_precision=2,
        value_fn=lambda device: device.grid.reactive_power_output_l2,
    ),
    SofarSensorDescription(
        key="power_factor_output_l2",
        component="grid",
        translation_key="power_factor_output_l2",
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.grid.power_factor_output_l2,
    ),
    SofarSensorDescription(
        key="current_pcc_l2",
        component="grid",
        translation_key="current_pcc_l2",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.grid.current_pcc_l2,
    ),
    SofarSensorDescription(
        key="active_power_pcc_l2",
        component="grid",
        translation_key="active_power_pcc_l2",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.grid.active_power_pcc_l2,
    ),
    SofarSensorDescription(
        key="reactive_power_pcc_l2",
        component="grid",
        translation_key="reactive_power_pcc_l2",
        device_class=SensorDeviceClass.REACTIVE_POWER,
        native_unit_of_measurement=UnitOfReactivePower.KILO_VOLT_AMPERE_REACTIVE,
        entity_registry_enabled_default=False,
        suggested_display_precision=2,
        value_fn=lambda device: device.grid.reactive_power_pcc_l2,
    ),
    SofarSensorDescription(
        key="power_factor_pcc_l2",
        component="grid",
        translation_key="power_factor_pcc_l2",
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.grid.power_factor_pcc_l2,
    ),
    SofarSensorDescription(
        key="voltage_l3",
        component="grid",
        translation_key="voltage_l3",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.grid.voltage_l3,
    ),
    SofarSensorDescription(
        key="current_output_l3",
        component="grid",
        translation_key="current_output_l3",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.grid.current_output_l3,
    ),
    SofarSensorDescription(
        key="active_power_output_l3",
        component="grid",
        translation_key="active_power_output_l3",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.grid.active_power_output_l3,
    ),
    SofarSensorDescription(
        key="reactive_power_output_l3",
        component="grid",
        translation_key="reactive_power_output_l3",
        device_class=SensorDeviceClass.REACTIVE_POWER,
        native_unit_of_measurement=UnitOfReactivePower.KILO_VOLT_AMPERE_REACTIVE,
        entity_registry_enabled_default=False,
        suggested_display_precision=2,
        value_fn=lambda device: device.grid.reactive_power_output_l3,
    ),
    SofarSensorDescription(
        key="power_factor_output_l3",
        component="grid",
        translation_key="power_factor_output_l3",
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.grid.power_factor_output_l3,
    ),
    SofarSensorDescription(
        key="current_pcc_l3",
        component="grid",
        translation_key="current_pcc_l3",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.grid.current_pcc_l3,
    ),
    SofarSensorDescription(
        key="active_power_pcc_l3",
        component="grid",
        translation_key="active_power_pcc_l3",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.grid.active_power_pcc_l3,
    ),
    SofarSensorDescription(
        key="reactive_power_pcc_l3",
        component="grid",
        translation_key="reactive_power_pcc_l3",
        device_class=SensorDeviceClass.REACTIVE_POWER,
        native_unit_of_measurement=UnitOfReactivePower.KILO_VOLT_AMPERE_REACTIVE,
        entity_registry_enabled_default=False,
        suggested_display_precision=2,
        value_fn=lambda device: device.grid.reactive_power_pcc_l3,
    ),
    SofarSensorDescription(
        key="power_factor_pcc_l3",
        component="grid",
        translation_key="power_factor_pcc_l3",
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.grid.power_factor_pcc_l3,
    ),
    SofarSensorDescription(
        key="active_power_pv_ext",
        component="grid",
        translation_key="active_power_pv_ext",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda device: device.grid.active_power_pv_ext,
    ),
    SofarSensorDescription(
        key="active_power_load_sys",
        component="grid",
        translation_key="active_power_load_sys",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda device: device.grid.active_power_load_sys,
    ),
    SofarSensorDescription(
        key="voltage_phase_l1n",
        component="grid",
        translation_key="voltage_phase_l1n",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.grid.voltage_phase_l1n,
    ),
    SofarSensorDescription(
        key="current_output_l1n",
        component="grid",
        translation_key="current_output_l1n",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.grid.current_output_l1n,
    ),
    SofarSensorDescription(
        key="active_power_output_l1n",
        component="grid",
        translation_key="active_power_output_l1n",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.grid.active_power_output_l1n,
    ),
    SofarSensorDescription(
        key="current_pcc_l1n",
        component="grid",
        translation_key="current_pcc_l1n",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.grid.current_pcc_l1n,
    ),
    SofarSensorDescription(
        key="active_power_pcc_l1n",
        component="grid",
        translation_key="active_power_pcc_l1n",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.grid.active_power_pcc_l1n,
    ),
    SofarSensorDescription(
        key="voltage_phase_l2n",
        component="grid",
        translation_key="voltage_phase_l2n",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.grid.voltage_phase_l2n,
    ),
    SofarSensorDescription(
        key="current_output_l2n",
        component="grid",
        translation_key="current_output_l2n",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.grid.current_output_l2n,
    ),
    SofarSensorDescription(
        key="active_power_output_l2n",
        component="grid",
        translation_key="active_power_output_l2n",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.grid.active_power_output_l2n,
    ),
    SofarSensorDescription(
        key="current_pcc_l2n",
        component="grid",
        translation_key="current_pcc_l2n",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.grid.current_pcc_l2n,
    ),
    SofarSensorDescription(
        key="active_power_pcc_l2n",
        component="grid",
        translation_key="active_power_pcc_l2n",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.grid.active_power_pcc_l2n,
    ),
    SofarSensorDescription(
        key="voltage_line_l1",
        component="grid",
        translation_key="voltage_line_l1",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.grid.voltage_line_l1,
    ),
    SofarSensorDescription(
        key="voltage_line_l2",
        component="grid",
        translation_key="voltage_line_l2",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.grid.voltage_line_l2,
    ),
    SofarSensorDescription(
        key="voltage_line_l3",
        component="grid",
        translation_key="voltage_line_l3",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.grid.voltage_line_l3,
    ),
    SofarSensorDescription(
        key="active_power_offgrid_total",
        component="offgrid",
        translation_key="active_power_offgrid_total",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda device: device.offgrid.active_power_offgrid_total,
    ),
    SofarSensorDescription(
        key="reactive_power_offgrid_total",
        component="offgrid",
        translation_key="reactive_power_offgrid_total",
        device_class=SensorDeviceClass.REACTIVE_POWER,
        native_unit_of_measurement=UnitOfReactivePower.KILO_VOLT_AMPERE_REACTIVE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        suggested_display_precision=2,
        value_fn=lambda device: device.offgrid.reactive_power_offgrid_total,
    ),
    SofarSensorDescription(
        key="apparent_power_offgrid_total",
        component="offgrid",
        translation_key="apparent_power_offgrid_total",
        device_class=SensorDeviceClass.APPARENT_POWER,
        native_unit_of_measurement=UnitOfApparentPower.KILO_VOLT_AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda device: device.offgrid.apparent_power_offgrid_total,
    ),
    SofarSensorDescription(
        key="offgrid_frequency",
        component="offgrid",
        translation_key="offgrid_frequency",
        device_class=SensorDeviceClass.FREQUENCY,
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        suggested_display_precision=2,
        value_fn=lambda device: device.offgrid.offgrid_frequency,
    ),
    SofarSensorDescription(
        key="offgrid_voltage",
        component="offgrid_single_phase",
        translation_key="offgrid_voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda device: device.offgrid_single_phase.offgrid_voltage,
    ),
    SofarSensorDescription(
        key="offgrid_voltage_l1",
        component="offgrid_three_phase",
        translation_key="offgrid_voltage_l1",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.offgrid_three_phase.offgrid_voltage_l1,
    ),
    SofarSensorDescription(
        key="offgrid_current_output",
        component="offgrid_single_phase",
        translation_key="offgrid_current_output",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda device: device.offgrid_single_phase.offgrid_current_output,
    ),
    SofarSensorDescription(
        key="offgrid_current_output_l1",
        component="offgrid_three_phase",
        translation_key="offgrid_current_output_l1",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.offgrid_three_phase.offgrid_current_output_l1,
    ),
    SofarSensorDescription(
        key="offgrid_active_power_output",
        component="offgrid_single_phase",
        translation_key="offgrid_active_power_output",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda device: device.offgrid_single_phase.offgrid_active_power_output,
    ),
    SofarSensorDescription(
        key="offgrid_active_power_output_l1",
        component="offgrid_three_phase",
        translation_key="offgrid_active_power_output_l1",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
        value_fn=lambda device: (
            device.offgrid_three_phase.offgrid_active_power_output_l1
        ),
    ),
    SofarSensorDescription(
        key="offgrid_reactive_power_output",
        component="offgrid_single_phase",
        translation_key="offgrid_reactive_power_output",
        device_class=SensorDeviceClass.REACTIVE_POWER,
        native_unit_of_measurement=UnitOfReactivePower.KILO_VOLT_AMPERE_REACTIVE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        suggested_display_precision=2,
        value_fn=lambda device: (
            device.offgrid_single_phase.offgrid_reactive_power_output
        ),
    ),
    SofarSensorDescription(
        key="offgrid_reactive_power_output_l1",
        component="offgrid_three_phase",
        translation_key="offgrid_reactive_power_output_l1",
        device_class=SensorDeviceClass.REACTIVE_POWER,
        native_unit_of_measurement=UnitOfReactivePower.KILO_VOLT_AMPERE_REACTIVE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        suggested_display_precision=2,
        value_fn=lambda device: (
            device.offgrid_three_phase.offgrid_reactive_power_output_l1
        ),
    ),
    SofarSensorDescription(
        key="offgrid_apparent_power_output",
        component="offgrid_single_phase",
        translation_key="offgrid_apparent_power_output",
        device_class=SensorDeviceClass.APPARENT_POWER,
        native_unit_of_measurement=UnitOfApparentPower.KILO_VOLT_AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda device: (
            device.offgrid_single_phase.offgrid_apparent_power_output
        ),
    ),
    SofarSensorDescription(
        key="offgrid_apparent_power_output_l1",
        component="offgrid_three_phase",
        translation_key="offgrid_apparent_power_output_l1",
        device_class=SensorDeviceClass.APPARENT_POWER,
        native_unit_of_measurement=UnitOfApparentPower.KILO_VOLT_AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
        value_fn=lambda device: (
            device.offgrid_three_phase.offgrid_apparent_power_output_l1
        ),
    ),
    SofarSensorDescription(
        key="offgrid_load_peak_ratio",
        component="offgrid_single_phase",
        translation_key="offgrid_load_peak_ratio",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda device: device.offgrid_single_phase.offgrid_load_peak_ratio,
    ),
    SofarSensorDescription(
        key="offgrid_load_peak_ratio_l1",
        component="offgrid_three_phase",
        translation_key="offgrid_load_peak_ratio_l1",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.offgrid_three_phase.offgrid_load_peak_ratio_l1,
    ),
    SofarSensorDescription(
        key="offgrid_voltage_l2",
        component="offgrid_three_phase",
        translation_key="offgrid_voltage_l2",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.offgrid_three_phase.offgrid_voltage_l2,
    ),
    SofarSensorDescription(
        key="offgrid_current_output_l2",
        component="offgrid_three_phase",
        translation_key="offgrid_current_output_l2",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.offgrid_three_phase.offgrid_current_output_l2,
    ),
    SofarSensorDescription(
        key="offgrid_active_power_output_l2",
        component="offgrid_three_phase",
        translation_key="offgrid_active_power_output_l2",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
        value_fn=lambda device: (
            device.offgrid_three_phase.offgrid_active_power_output_l2
        ),
    ),
    SofarSensorDescription(
        key="offgrid_reactive_power_output_l2",
        component="offgrid_three_phase",
        translation_key="offgrid_reactive_power_output_l2",
        device_class=SensorDeviceClass.REACTIVE_POWER,
        native_unit_of_measurement=UnitOfReactivePower.KILO_VOLT_AMPERE_REACTIVE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        suggested_display_precision=2,
        value_fn=lambda device: (
            device.offgrid_three_phase.offgrid_reactive_power_output_l2
        ),
    ),
    SofarSensorDescription(
        key="offgrid_apparent_power_output_l2",
        component="offgrid_three_phase",
        translation_key="offgrid_apparent_power_output_l2",
        device_class=SensorDeviceClass.APPARENT_POWER,
        native_unit_of_measurement=UnitOfApparentPower.KILO_VOLT_AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
        value_fn=lambda device: (
            device.offgrid_three_phase.offgrid_apparent_power_output_l2
        ),
    ),
    SofarSensorDescription(
        key="offgrid_load_peak_ratio_l2",
        component="offgrid_three_phase",
        translation_key="offgrid_load_peak_ratio_l2",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.offgrid_three_phase.offgrid_load_peak_ratio_l2,
    ),
    SofarSensorDescription(
        key="offgrid_voltage_l3",
        component="offgrid_three_phase",
        translation_key="offgrid_voltage_l3",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.offgrid_three_phase.offgrid_voltage_l3,
    ),
    SofarSensorDescription(
        key="offgrid_current_output_l3",
        component="offgrid_three_phase",
        translation_key="offgrid_current_output_l3",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.offgrid_three_phase.offgrid_current_output_l3,
    ),
    SofarSensorDescription(
        key="offgrid_active_power_output_l3",
        component="offgrid_three_phase",
        translation_key="offgrid_active_power_output_l3",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
        value_fn=lambda device: (
            device.offgrid_three_phase.offgrid_active_power_output_l3
        ),
    ),
    SofarSensorDescription(
        key="offgrid_reactive_power_output_l3",
        component="offgrid_three_phase",
        translation_key="offgrid_reactive_power_output_l3",
        device_class=SensorDeviceClass.REACTIVE_POWER,
        native_unit_of_measurement=UnitOfReactivePower.KILO_VOLT_AMPERE_REACTIVE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        suggested_display_precision=2,
        value_fn=lambda device: (
            device.offgrid_three_phase.offgrid_reactive_power_output_l3
        ),
    ),
    SofarSensorDescription(
        key="offgrid_apparent_power_output_l3",
        component="offgrid_three_phase",
        translation_key="offgrid_apparent_power_output_l3",
        device_class=SensorDeviceClass.APPARENT_POWER,
        native_unit_of_measurement=UnitOfApparentPower.KILO_VOLT_AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
        value_fn=lambda device: (
            device.offgrid_three_phase.offgrid_apparent_power_output_l3
        ),
    ),
    SofarSensorDescription(
        key="offgrid_load_peak_ratio_l3",
        component="offgrid_three_phase",
        translation_key="offgrid_load_peak_ratio_l3",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.offgrid_three_phase.offgrid_load_peak_ratio_l3,
    ),
    SofarSensorDescription(
        key="offgrid_voltage_output_l1n",
        component="offgrid_three_phase",
        translation_key="offgrid_voltage_output_l1n",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.offgrid_three_phase.offgrid_voltage_output_l1n,
    ),
    SofarSensorDescription(
        key="offgrid_current_output_l1n",
        component="offgrid_three_phase",
        translation_key="offgrid_current_output_l1n",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.offgrid_three_phase.offgrid_current_output_l1n,
    ),
    SofarSensorDescription(
        key="offgrid_active_power_output_l1n",
        component="offgrid_three_phase",
        translation_key="offgrid_active_power_output_l1n",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
        value_fn=lambda device: (
            device.offgrid_three_phase.offgrid_active_power_output_l1n
        ),
    ),
    SofarSensorDescription(
        key="offgrid_voltage_output_l2n",
        component="offgrid_three_phase",
        translation_key="offgrid_voltage_output_l2n",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.offgrid_three_phase.offgrid_voltage_output_l2n,
    ),
    SofarSensorDescription(
        key="offgrid_current_output_l2n",
        component="offgrid_three_phase",
        translation_key="offgrid_current_output_l2n",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.offgrid_three_phase.offgrid_current_output_l2n,
    ),
    SofarSensorDescription(
        key="offgrid_active_power_output_l2n",
        component="offgrid_three_phase",
        translation_key="offgrid_active_power_output_l2n",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
        value_fn=lambda device: (
            device.offgrid_three_phase.offgrid_active_power_output_l2n
        ),
    ),
    SofarSensorDescription(
        key="battery_power_total",
        component="battery_totals",
        translation_key="battery_power_total",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda device: device.battery_totals.battery_power_total,
    ),
    SofarSensorDescription(
        key="battery_capacity_total",
        component="battery_totals",
        translation_key="battery_state_of_charge_total",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda device: device.battery_totals.battery_capacity_total,
    ),
    SofarSensorDescription(
        key="battery_state_of_health_total",
        component="battery_totals",
        translation_key="battery_state_of_health_total",
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda device: device.battery_totals.battery_state_of_health_total,
    ),
    SofarSensorDescription(
        key="passive_eps_wait_time",
        component="eps",
        translation_key="passive_eps_wait_time",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.eps.passive_eps_wait_time,
    ),
    SofarSensorDescription(
        key="bat_config_overvoltage_protection",
        component="battery_config_id",
        translation_key="bat_config_overvoltage_protection",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda device: (
            device.battery_config_id.bat_config_overvoltage_protection
        ),
    ),
    SofarSensorDescription(
        key="bat_config_charging_voltage",
        component="battery_config",
        translation_key="bat_config_charging_voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.battery_config.bat_config_charging_voltage,
    ),
    SofarSensorDescription(
        key="bat_config_undervoltage_protection",
        component="battery_config",
        translation_key="bat_config_undervoltage_protection",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda device: (
            device.battery_config.bat_config_undervoltage_protection
        ),
    ),
    SofarSensorDescription(
        key="bat_config_minimum_discharge_voltage",
        component="battery_config",
        translation_key="bat_config_minimum_discharge_voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda device: (
            device.battery_config.bat_config_minimum_discharge_voltage
        ),
    ),
    SofarSensorDescription(
        key="bat_config_maximum_charge_current_limit",
        component="battery_config",
        translation_key="bat_config_maximum_charge_current_limit",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        suggested_display_precision=2,
        value_fn=lambda device: (
            device.battery_config.bat_config_maximum_charge_current_limit
        ),
    ),
    SofarSensorDescription(
        key="bat_config_maximum_discharge_current_limit",
        component="battery_config",
        translation_key="bat_config_maximum_discharge_current_limit",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        suggested_display_precision=2,
        value_fn=lambda device: (
            device.battery_config.bat_config_maximum_discharge_current_limit
        ),
    ),
    SofarSensorDescription(
        key="bat_config_depth_of_discharge",
        component="battery_config",
        translation_key="bat_config_depth_of_discharge",
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.battery_config.bat_config_depth_of_discharge,
    ),
    SofarSensorDescription(
        key="bat_config_end_of_discharge",
        component="battery_config",
        translation_key="bat_config_end_of_discharge",
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.battery_config.bat_config_end_of_discharge,
    ),
    SofarSensorDescription(
        key="bat_config_capacity",
        component="battery_config",
        translation_key="bat_config_capacity",
        native_unit_of_measurement="Ah",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.battery_config.bat_config_capacity,
    ),
    SofarSensorDescription(
        key="bat_config_rated_battery_voltage",
        component="battery_config",
        translation_key="bat_config_rated_battery_voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.battery_config.bat_config_rated_battery_voltage,
    ),
    SofarSensorDescription(
        key="bat_config_eps_buffer",
        component="battery_config",
        translation_key="bat_config_eps_buffer",
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.battery_config.bat_config_eps_buffer,
    ),
    SofarSensorDescription(
        key="bat_config_tempco",
        component="battery_config",
        translation_key="bat_config_tempco",
        native_unit_of_measurement="mV/Cell",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.battery_config.bat_config_tempco,
    ),
    SofarSensorDescription(
        key="bat_config_voltage_float",
        component="battery_config",
        translation_key="bat_config_voltage_float",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.battery_config.bat_config_voltage_float,
    ),
    SofarSensorDescription(
        key="on_grid_discharge_cutoff_soc",
        component="battery_config",
        translation_key="on_grid_discharge_cutoff_soc",
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.battery_config.on_grid_discharge_cutoff_soc,
    ),
    SofarSensorDescription(
        key="off_grid_discharge_cutoff_soc",
        component="battery_config",
        translation_key="off_grid_discharge_cutoff_soc",
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.battery_config.off_grid_discharge_cutoff_soc,
    ),
    SofarSensorDescription(
        key="off_grid_recovery_soc",
        component="battery_config",
        translation_key="off_grid_recovery_soc",
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.battery_config.off_grid_recovery_soc,
    ),
    SofarSensorDescription(
        key="bat_config_charge_cutoff_soc",
        component="battery_charge_cutoff",
        translation_key="bat_config_charge_cutoff_soc",
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda device: (
            device.battery_charge_cutoff.bat_config_charge_cutoff_soc
        ),
    ),
    SofarSensorDescription(
        key="feedin_max_power",
        component="feed_in",
        translation_key="feedin_max_power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.feed_in.feedin_max_power,
    ),
    SofarSensorDescription(
        key="active_power_export_limit",
        component="active_power_control",
        translation_key="active_power_export_limit",
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.active_power_control.active_power_export_limit,
    ),
    SofarSensorDescription(
        key="passive_mode_timeout",
        component="passive",
        translation_key="passive_mode_timeout",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.passive.passive_mode_timeout,
    ),
    SofarSensorDescription(
        key="passive_mode_grid_power",
        component="passive",
        translation_key="passive_mode_grid_power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.passive.passive_mode_grid_power,
    ),
    SofarSensorDescription(
        key="passive_mode_battery_power_min",
        component="passive",
        translation_key="passive_mode_battery_power_min",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.passive.passive_mode_battery_power_min,
    ),
    SofarSensorDescription(
        key="passive_mode_battery_power_max",
        component="passive",
        translation_key="passive_mode_battery_power_max",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.passive.passive_mode_battery_power_max,
    ),
)

SENSOR_DESCRIPTIONS += _part_sensors(
    "pv_string", PV_STRING_COMPONENTS, _PV_STRING_MEASUREMENTS
) + _part_sensors("battery", BATTERY_STRING_COMPONENTS, _BATTERY_MEASUREMENTS)

ENUM_SENSOR_DESCRIPTIONS: tuple[SofarEnumSensorDescription, ...] = (
    SofarEnumSensorDescription(
        key="system_state",
        component="state",
        translation_key="system_state",
        device_class=SensorDeviceClass.ENUM,
        options=enum_options(SystemState),
        value_fn=lambda device: device.state.system_state,
    ),
    SofarEnumSensorDescription(
        key="bat_config_protocol",
        component="battery_config_id",
        translation_key="bat_config_protocol",
        device_class=SensorDeviceClass.ENUM,
        options=enum_options(BatteryConfigProtocol),
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.battery_config_id.bat_config_protocol,
    ),
    SofarEnumSensorDescription(
        key="bat_config_cell_type",
        component="battery_config",
        translation_key="bat_config_cell_type",
        device_class=SensorDeviceClass.ENUM,
        options=enum_options(BatteryConfigCellType),
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.battery_config.bat_config_cell_type,
    ),
    SofarEnumSensorDescription(
        key="sync_rtc_result",
        component="rtc_sync",
        translation_key="sync_rtc_result",
        device_class=SensorDeviceClass.ENUM,
        options=enum_options(SyncRtcResult),
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda device: device.rtc_sync.sync_rtc_result,
    ),
    SofarEnumSensorDescription(
        key="feedin_limitation_mode",
        component="feed_in",
        translation_key="feedin_limitation_mode",
        device_class=SensorDeviceClass.ENUM,
        options=enum_options(FeedInLimitationMode),
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.feed_in.feedin_limitation_mode,
    ),
    SofarEnumSensorDescription(
        key="passive_mode_timeout_action",
        component="passive",
        translation_key="passive_mode_timeout_action",
        device_class=SensorDeviceClass.ENUM,
        options=enum_options(PassiveModeTimeoutAction),
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.passive.passive_mode_timeout_action,
    ),
)

TOTAL_SENSOR_DESCRIPTIONS: tuple[SofarTotalSensorDescription, ...] = (
    SofarTotalSensorDescription(
        key="solar_generation_total",
        component="energy",
        translation_key="solar_generation_total",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
        total_fn=lambda device: device.energy.solar_generation_total_corrected,
    ),
    SofarTotalSensorDescription(
        key="solar_generation_today",
        component="energy",
        translation_key="solar_generation_today",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
        total_fn=lambda device: device.energy.solar_generation_today_corrected,
    ),
    SofarTotalSensorDescription(
        key="load_consumption_today",
        component="meter_energy",
        translation_key="load_consumption_today",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
        total_fn=lambda device: device.meter_energy.load_consumption_today_corrected,
    ),
    SofarTotalSensorDescription(
        key="load_consumption_total",
        component="meter_energy",
        translation_key="load_consumption_total",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
        total_fn=lambda device: device.meter_energy.load_consumption_total_corrected,
    ),
    SofarTotalSensorDescription(
        key="import_energy_today",
        component="meter_energy",
        translation_key="import_energy_today",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
        total_fn=lambda device: device.meter_energy.import_energy_today_corrected,
    ),
    SofarTotalSensorDescription(
        key="import_energy_total",
        component="meter_energy",
        translation_key="import_energy_total",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
        total_fn=lambda device: device.meter_energy.import_energy_total_corrected,
    ),
    SofarTotalSensorDescription(
        key="export_energy_today",
        component="meter_energy",
        translation_key="export_energy_today",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
        total_fn=lambda device: device.meter_energy.export_energy_today_corrected,
    ),
    SofarTotalSensorDescription(
        key="export_energy_total",
        component="meter_energy",
        translation_key="export_energy_total",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
        total_fn=lambda device: device.meter_energy.export_energy_total_corrected,
    ),
    SofarTotalSensorDescription(
        key="battery_input_energy_today",
        component="battery_energy",
        translation_key="battery_input_energy_today",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
        total_fn=lambda device: (
            device.battery_energy.battery_input_energy_today_corrected
        ),
    ),
    SofarTotalSensorDescription(
        key="battery_input_energy_total",
        component="battery_energy",
        translation_key="battery_input_energy_total",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
        total_fn=lambda device: (
            device.battery_energy.battery_input_energy_total_corrected
        ),
    ),
    SofarTotalSensorDescription(
        key="battery_output_energy_today",
        component="battery_energy",
        translation_key="battery_output_energy_today",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
        total_fn=lambda device: (
            device.battery_energy.battery_output_energy_today_corrected
        ),
    ),
    SofarTotalSensorDescription(
        key="battery_output_energy_total",
        component="battery_energy",
        translation_key="battery_output_energy_total",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
        total_fn=lambda device: (
            device.battery_energy.battery_output_energy_total_corrected
        ),
    ),
)


def _cell_voltage(cell: int) -> SofarPackSensorDescription:
    """Describe one cell's voltage, shown only for cells the pack has."""
    return SofarPackSensorDescription(
        key=f"cell_voltage_{cell}",
        component=BATTERY_PACKS,
        translation_key="cell_voltage",
        translation_placeholders={"cell": str(cell)},
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        exists_fn=lambda pack: (
            pack.cells_in_pack is not None and cell <= pack.cells_in_pack
        ),
        value_fn=lambda pack: pack.cell_voltages[cell - 1],
    )


def _cell_temperature(sensor: int) -> SofarPackSensorDescription:
    """Describe one of the pack's four cell temperature sensors."""
    return SofarPackSensorDescription(
        key=f"cell_temperature_{sensor}",
        component=BATTERY_PACKS,
        translation_key="cell_temperature",
        translation_placeholders={"sensor": str(sensor)},
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda pack: pack.cell_temperatures[sensor - 1],
    )


PACK_SENSOR_DESCRIPTIONS: tuple[SofarPackSensorDescription, ...] = (
    SofarPackSensorDescription(
        key="remaining_capacity",
        component=BATTERY_PACKS,
        translation_key="remaining_capacity",
        native_unit_of_measurement="Ah",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda pack: pack.pack_remaining_capacity,
    ),
    SofarPackSensorDescription(
        key="full_charge_capacity",
        component=BATTERY_PACKS,
        translation_key="full_charge_capacity",
        native_unit_of_measurement="Ah",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda pack: pack.pack_full_charge_capacity,
    ),
    SofarPackSensorDescription(
        key="charge_cycle",
        component=BATTERY_PACKS,
        translation_key="charge_cycle",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda pack: pack.pack_cycles,
    ),
    SofarPackSensorDescription(
        key="cell_voltage_max",
        component=BATTERY_PACKS,
        translation_key="cell_voltage_max",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda pack: pack.cell_max_voltage,
    ),
    SofarPackSensorDescription(
        key="cell_voltage_min",
        component=BATTERY_PACKS,
        translation_key="cell_voltage_min",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda pack: pack.cell_min_voltage,
    ),
    SofarPackSensorDescription(
        key="mosfet_temperature",
        component=BATTERY_PACKS,
        translation_key="mosfet_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda pack: pack.pack_temperature_mos,
    ),
    SofarPackSensorDescription(
        key="internal_temperature",
        component=BATTERY_PACKS,
        translation_key="internal_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda pack: pack.pack_temperature_env,
    ),
    *(_cell_temperature(sensor) for sensor in range(1, 5)),
    *(_cell_voltage(cell) for cell in range(1, 25)),
)
