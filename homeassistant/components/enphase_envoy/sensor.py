"""Support for Enphase Envoy solar energy monitor."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
import datetime
import logging
from operator import attrgetter
from typing import TYPE_CHECKING

from pyenphase import (
    EnvoyEncharge,
    EnvoyEnchargeAggregate,
    EnvoyEnchargePower,
    EnvoyEnpower,
    EnvoyInverter,
    EnvoySystemConsumption,
    EnvoySystemProduction,
)
from pyenphase.const import PHASENAMES
from pyenphase.models.meters import (
    CtMeterStatus,
    CtState,
    CtStatusFlags,
    CtType,
    EnvoyMeterData,
)

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    UnitOfApparentPower,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .coordinator import EnphaseUpdateCoordinator
from .entity import EnvoyBaseEntity

ICON = "mdi:flash"
_LOGGER = logging.getLogger(__name__)

INVERTERS_KEY = "inverters"
LAST_REPORTED_KEY = "last_reported"


@dataclass(frozen=True, kw_only=True)
class EnvoyInverterSensorEntityDescription(SensorEntityDescription):
    """Describes an Envoy inverter sensor entity."""

    value_fn: Callable[[EnvoyInverter], datetime.datetime | float]


INVERTER_SENSORS = (
    EnvoyInverterSensorEntityDescription(
        key=INVERTERS_KEY,
        name=None,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
        value_fn=attrgetter("last_report_watts"),
    ),
    EnvoyInverterSensorEntityDescription(
        key=LAST_REPORTED_KEY,
        translation_key=LAST_REPORTED_KEY,
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_registry_enabled_default=False,
        value_fn=lambda inverter: dt_util.utc_from_timestamp(inverter.last_report_date),
    ),
)


@dataclass(frozen=True, kw_only=True)
class EnvoyProductionSensorEntityDescription(SensorEntityDescription):
    """Describes an Envoy production sensor entity."""

    value_fn: Callable[[EnvoySystemProduction], int]
    on_phase: str | None


PRODUCTION_SENSORS = (
    EnvoyProductionSensorEntityDescription(
        key="production",
        translation_key="current_power_production",
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
        suggested_unit_of_measurement=UnitOfPower.KILO_WATT,
        suggested_display_precision=3,
        value_fn=attrgetter("watts_now"),
        on_phase=None,
    ),
    EnvoyProductionSensorEntityDescription(
        key="daily_production",
        translation_key="daily_production",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_class=SensorDeviceClass.ENERGY,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=2,
        value_fn=attrgetter("watt_hours_today"),
        on_phase=None,
    ),
    EnvoyProductionSensorEntityDescription(
        key="seven_days_production",
        translation_key="seven_days_production",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=1,
        value_fn=attrgetter("watt_hours_last_7_days"),
        on_phase=None,
    ),
    EnvoyProductionSensorEntityDescription(
        key="lifetime_production",
        translation_key="lifetime_production",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_class=SensorDeviceClass.ENERGY,
        suggested_unit_of_measurement=UnitOfEnergy.MEGA_WATT_HOUR,
        suggested_display_precision=3,
        value_fn=attrgetter("watt_hours_lifetime"),
        on_phase=None,
    ),
)


PRODUCTION_PHASE_SENSORS = {
    (on_phase := PHASENAMES[phase]): [
        replace(
            sensor,
            key=f"{sensor.key}_l{phase + 1}",
            translation_key=f"{sensor.translation_key}_phase",
            entity_registry_enabled_default=False,
            on_phase=on_phase,
            translation_placeholders={"phase_name": f"l{phase + 1}"},
        )
        for sensor in list(PRODUCTION_SENSORS)
    ]
    for phase in range(3)
}


@dataclass(frozen=True, kw_only=True)
class EnvoyConsumptionSensorEntityDescription(SensorEntityDescription):
    """Describes an Envoy consumption sensor entity."""

    value_fn: Callable[[EnvoySystemConsumption], int]
    on_phase: str | None


CONSUMPTION_SENSORS = (
    EnvoyConsumptionSensorEntityDescription(
        key="consumption",
        translation_key="current_power_consumption",
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
        suggested_unit_of_measurement=UnitOfPower.KILO_WATT,
        suggested_display_precision=3,
        value_fn=attrgetter("watts_now"),
        on_phase=None,
    ),
    EnvoyConsumptionSensorEntityDescription(
        key="daily_consumption",
        translation_key="daily_consumption",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_class=SensorDeviceClass.ENERGY,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=2,
        value_fn=attrgetter("watt_hours_today"),
        on_phase=None,
    ),
    EnvoyConsumptionSensorEntityDescription(
        key="seven_days_consumption",
        translation_key="seven_days_consumption",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=1,
        value_fn=attrgetter("watt_hours_last_7_days"),
        on_phase=None,
    ),
    EnvoyConsumptionSensorEntityDescription(
        key="lifetime_consumption",
        translation_key="lifetime_consumption",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_class=SensorDeviceClass.ENERGY,
        suggested_unit_of_measurement=UnitOfEnergy.MEGA_WATT_HOUR,
        suggested_display_precision=3,
        value_fn=attrgetter("watt_hours_lifetime"),
        on_phase=None,
    ),
)


CONSUMPTION_PHASE_SENSORS = {
    (on_phase := PHASENAMES[phase]): [
        replace(
            sensor,
            key=f"{sensor.key}_l{phase + 1}",
            translation_key=f"{sensor.translation_key}_phase",
            entity_registry_enabled_default=False,
            on_phase=on_phase,
            translation_placeholders={"phase_name": f"l{phase + 1}"},
        )
        for sensor in list(CONSUMPTION_SENSORS)
    ]
    for phase in range(3)
}


@dataclass(frozen=True, kw_only=True)
class EnvoyCTSensorEntityDescription(SensorEntityDescription):
    """Describes an Envoy CT sensor entity."""

    value_fn: Callable[
        [EnvoyMeterData],
        int | float | str | CtType | CtMeterStatus | CtStatusFlags | CtState | None,
    ]
    on_phase: str | None


CT_NET_CONSUMPTION_SENSORS = (
    EnvoyCTSensorEntityDescription(
        key="lifetime_net_consumption",
        translation_key="lifetime_net_consumption",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_class=SensorDeviceClass.ENERGY,
        suggested_unit_of_measurement=UnitOfEnergy.MEGA_WATT_HOUR,
        suggested_display_precision=3,
        value_fn=attrgetter("energy_delivered"),
        on_phase=None,
    ),
    EnvoyCTSensorEntityDescription(
        key="lifetime_net_production",
        translation_key="lifetime_net_production",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_class=SensorDeviceClass.ENERGY,
        suggested_unit_of_measurement=UnitOfEnergy.MEGA_WATT_HOUR,
        suggested_display_precision=3,
        value_fn=attrgetter("energy_received"),
        on_phase=None,
    ),
    EnvoyCTSensorEntityDescription(
        key="net_consumption",
        translation_key="net_consumption",
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
        suggested_unit_of_measurement=UnitOfPower.KILO_WATT,
        suggested_display_precision=3,
        value_fn=attrgetter("active_power"),
        on_phase=None,
    ),
    EnvoyCTSensorEntityDescription(
        key="frequency",
        translation_key="net_ct_frequency",
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.FREQUENCY,
        suggested_display_precision=1,
        entity_registry_enabled_default=False,
        value_fn=attrgetter("frequency"),
        on_phase=None,
    ),
    EnvoyCTSensorEntityDescription(
        key="voltage",
        translation_key="net_ct_voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.VOLTAGE,
        suggested_unit_of_measurement=UnitOfElectricPotential.VOLT,
        suggested_display_precision=1,
        entity_registry_enabled_default=False,
        value_fn=attrgetter("voltage"),
        on_phase=None,
    ),
    EnvoyCTSensorEntityDescription(
        key="net_consumption_ct_metering_status",
        translation_key="net_ct_metering_status",
        device_class=SensorDeviceClass.ENUM,
        options=list(CtMeterStatus),
        entity_registry_enabled_default=False,
        value_fn=attrgetter("metering_status"),
        on_phase=None,
    ),
    EnvoyCTSensorEntityDescription(
        key="net_consumption_ct_status_flags",
        translation_key="net_ct_status_flags",
        state_class=None,
        entity_registry_enabled_default=False,
        value_fn=lambda ct: 0 if ct.status_flags is None else len(ct.status_flags),
        on_phase=None,
    ),
)


CT_NET_CONSUMPTION_PHASE_SENSORS = {
    (on_phase := PHASENAMES[phase]): [
        replace(
            sensor,
            key=f"{sensor.key}_l{phase + 1}",
            translation_key=f"{sensor.translation_key}_phase",
            entity_registry_enabled_default=False,
            on_phase=on_phase,
            translation_placeholders={"phase_name": f"l{phase + 1}"},
        )
        for sensor in list(CT_NET_CONSUMPTION_SENSORS)
    ]
    for phase in range(3)
}

CT_PRODUCTION_SENSORS = (
    EnvoyCTSensorEntityDescription(
        key="production_ct_metering_status",
        translation_key="production_ct_metering_status",
        device_class=SensorDeviceClass.ENUM,
        options=list(CtMeterStatus),
        entity_registry_enabled_default=False,
        value_fn=attrgetter("metering_status"),
        on_phase=None,
    ),
    EnvoyCTSensorEntityDescription(
        key="production_ct_status_flags",
        translation_key="production_ct_status_flags",
        state_class=None,
        entity_registry_enabled_default=False,
        value_fn=lambda ct: 0 if ct.status_flags is None else len(ct.status_flags),
        on_phase=None,
    ),
)

CT_PRODUCTION_PHASE_SENSORS = {
    (on_phase := PHASENAMES[phase]): [
        replace(
            sensor,
            key=f"{sensor.key}_l{phase + 1}",
            translation_key=f"{sensor.translation_key}_phase",
            entity_registry_enabled_default=False,
            on_phase=on_phase,
            translation_placeholders={"phase_name": f"l{phase + 1}"},
        )
        for sensor in list(CT_PRODUCTION_SENSORS)
    ]
    for phase in range(3)
}

CT_STORAGE_SENSORS = (
    EnvoyCTSensorEntityDescription(
        key="lifetime_battery_discharged",
        translation_key="lifetime_battery_discharged",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_class=SensorDeviceClass.ENERGY,
        suggested_unit_of_measurement=UnitOfEnergy.MEGA_WATT_HOUR,
        suggested_display_precision=3,
        value_fn=attrgetter("energy_delivered"),
        on_phase=None,
    ),
    EnvoyCTSensorEntityDescription(
        key="lifetime_battery_charged",
        translation_key="lifetime_battery_charged",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_class=SensorDeviceClass.ENERGY,
        suggested_unit_of_measurement=UnitOfEnergy.MEGA_WATT_HOUR,
        suggested_display_precision=3,
        value_fn=attrgetter("energy_received"),
        on_phase=None,
    ),
    EnvoyCTSensorEntityDescription(
        key="battery_discharge",
        translation_key="battery_discharge",
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
        suggested_unit_of_measurement=UnitOfPower.KILO_WATT,
        suggested_display_precision=3,
        value_fn=attrgetter("active_power"),
        on_phase=None,
    ),
    EnvoyCTSensorEntityDescription(
        key="storage_voltage",
        translation_key="storage_ct_voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.VOLTAGE,
        suggested_unit_of_measurement=UnitOfElectricPotential.VOLT,
        suggested_display_precision=1,
        entity_registry_enabled_default=False,
        value_fn=attrgetter("voltage"),
        on_phase=None,
    ),
    EnvoyCTSensorEntityDescription(
        key="storage_ct_metering_status",
        translation_key="storage_ct_metering_status",
        device_class=SensorDeviceClass.ENUM,
        options=list(CtMeterStatus),
        entity_registry_enabled_default=False,
        value_fn=attrgetter("metering_status"),
        on_phase=None,
    ),
    EnvoyCTSensorEntityDescription(
        key="storage_ct_status_flags",
        translation_key="storage_ct_status_flags",
        state_class=None,
        entity_registry_enabled_default=False,
        value_fn=lambda ct: 0 if ct.status_flags is None else len(ct.status_flags),
        on_phase=None,
    ),
)


CT_STORAGE_PHASE_SENSORS = {
    (on_phase := PHASENAMES[phase]): [
        replace(
            sensor,
            key=f"{sensor.key}_l{phase + 1}",
            translation_key=f"{sensor.translation_key}_phase",
            entity_registry_enabled_default=False,
            on_phase=on_phase,
            translation_placeholders={"phase_name": f"l{phase + 1}"},
        )
        for sensor in list(CT_STORAGE_SENSORS)
    ]
    for phase in range(3)
}


@dataclass(frozen=True, kw_only=True)
class EnvoyEnchargeSensorEntityDescription(SensorEntityDescription):
    """Describes an Envoy Encharge sensor entity."""

    value_fn: Callable[[EnvoyEncharge], datetime.datetime | int | float]


@dataclass(frozen=True)
class EnvoyEnchargePowerRequiredKeysMixin:
    """Mixin for required keys."""


@dataclass(frozen=True, kw_only=True)
class EnvoyEnchargePowerSensorEntityDescription(SensorEntityDescription):
    """Describes an Envoy Encharge sensor entity."""

    value_fn: Callable[[EnvoyEnchargePower], int | float]


ENCHARGE_INVENTORY_SENSORS = (
    EnvoyEnchargeSensorEntityDescription(
        key="temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        value_fn=attrgetter("temperature"),
    ),
    EnvoyEnchargeSensorEntityDescription(
        key=LAST_REPORTED_KEY,
        translation_key=LAST_REPORTED_KEY,
        native_unit_of_measurement=None,
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda encharge: dt_util.utc_from_timestamp(encharge.last_report_date),
    ),
)
ENCHARGE_POWER_SENSORS = (
    EnvoyEnchargePowerSensorEntityDescription(
        key="soc",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        value_fn=attrgetter("soc"),
    ),
    EnvoyEnchargePowerSensorEntityDescription(
        key="apparent_power_mva",
        native_unit_of_measurement=UnitOfApparentPower.VOLT_AMPERE,
        device_class=SensorDeviceClass.APPARENT_POWER,
        value_fn=lambda encharge: encharge.apparent_power_mva * 0.001,
    ),
    EnvoyEnchargePowerSensorEntityDescription(
        key="real_power_mw",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        value_fn=lambda encharge: encharge.real_power_mw * 0.001,
    ),
)


@dataclass(frozen=True, kw_only=True)
class EnvoyEnpowerSensorEntityDescription(SensorEntityDescription):
    """Describes an Envoy Encharge sensor entity."""

    value_fn: Callable[[EnvoyEnpower], datetime.datetime | int | float]


ENPOWER_SENSORS = (
    EnvoyEnpowerSensorEntityDescription(
        key="temperature",
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        device_class=SensorDeviceClass.TEMPERATURE,
        value_fn=attrgetter("temperature"),
    ),
    EnvoyEnpowerSensorEntityDescription(
        key=LAST_REPORTED_KEY,
        translation_key=LAST_REPORTED_KEY,
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda enpower: dt_util.utc_from_timestamp(enpower.last_report_date),
    ),
)


@dataclass(frozen=True)
class EnvoyEnchargeAggregateRequiredKeysMixin:
    """Mixin for required keys."""


@dataclass(frozen=True, kw_only=True)
class EnvoyEnchargeAggregateSensorEntityDescription(SensorEntityDescription):
    """Describes an Envoy Encharge sensor entity."""

    value_fn: Callable[[EnvoyEnchargeAggregate], int]


ENCHARGE_AGGREGATE_SENSORS = (
    EnvoyEnchargeAggregateSensorEntityDescription(
        key="battery_level",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        value_fn=attrgetter("state_of_charge"),
    ),
    EnvoyEnchargeAggregateSensorEntityDescription(
        key="reserve_soc",
        translation_key="reserve_soc",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        value_fn=attrgetter("reserve_state_of_charge"),
    ),
    EnvoyEnchargeAggregateSensorEntityDescription(
        key="available_energy",
        translation_key="available_energy",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        value_fn=attrgetter("available_energy"),
    ),
    EnvoyEnchargeAggregateSensorEntityDescription(
        key="reserve_energy",
        translation_key="reserve_energy",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        value_fn=attrgetter("backup_reserve"),
    ),
    EnvoyEnchargeAggregateSensorEntityDescription(
        key="max_capacity",
        translation_key="max_capacity",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        value_fn=attrgetter("max_available_capacity"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up envoy sensor platform."""
    coordinator: EnphaseUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    envoy_data = coordinator.envoy.data
    assert envoy_data is not None
    _LOGGER.debug("Envoy data: %s", envoy_data)

    entities: list[Entity] = [
        EnvoyProductionEntity(coordinator, description)
        for description in PRODUCTION_SENSORS
    ]
    if envoy_data.system_consumption:
        entities.extend(
            EnvoyConsumptionEntity(coordinator, description)
            for description in CONSUMPTION_SENSORS
        )
    # For each production phase reported add production entities
    if envoy_data.system_production_phases:
        entities.extend(
            EnvoyProductionPhaseEntity(coordinator, description)
            for use_phase, phase in envoy_data.system_production_phases.items()
            for description in PRODUCTION_PHASE_SENSORS[use_phase]
            if phase is not None
        )
    # For each consumption phase reported add consumption entities
    if envoy_data.system_consumption_phases:
        entities.extend(
            EnvoyConsumptionPhaseEntity(coordinator, description)
            for use_phase, phase in envoy_data.system_consumption_phases.items()
            for description in CONSUMPTION_PHASE_SENSORS[use_phase]
            if phase is not None
        )
    # Add net consumption CT entities
    if ctmeter := envoy_data.ctmeter_consumption:
        entities.extend(
            EnvoyConsumptionCTEntity(coordinator, description)
            for description in CT_NET_CONSUMPTION_SENSORS
            if ctmeter.measurement_type == CtType.NET_CONSUMPTION
        )
    # For each net consumption ct phase reported add net consumption entities
    if phase_data := envoy_data.ctmeter_consumption_phases:
        entities.extend(
            EnvoyConsumptionCTPhaseEntity(coordinator, description)
            for use_phase, phase in phase_data.items()
            for description in CT_NET_CONSUMPTION_PHASE_SENSORS[use_phase]
            if phase.measurement_type == CtType.NET_CONSUMPTION
        )
    # Add production CT entities
    if ctmeter := envoy_data.ctmeter_production:
        entities.extend(
            EnvoyProductionCTEntity(coordinator, description)
            for description in CT_PRODUCTION_SENSORS
            if ctmeter.measurement_type == CtType.PRODUCTION
        )
    # For each production ct phase reported add production ct entities
    if phase_data := envoy_data.ctmeter_production_phases:
        entities.extend(
            EnvoyProductionCTPhaseEntity(coordinator, description)
            for use_phase, phase in phase_data.items()
            for description in CT_PRODUCTION_PHASE_SENSORS[use_phase]
            if phase.measurement_type == CtType.PRODUCTION
        )
    # Add storage CT entities
    if ctmeter := envoy_data.ctmeter_storage:
        entities.extend(
            EnvoyStorageCTEntity(coordinator, description)
            for description in CT_STORAGE_SENSORS
            if ctmeter.measurement_type == CtType.STORAGE
        )
    # For each storage ct phase reported add storage ct entities
    if phase_data := envoy_data.ctmeter_storage_phases:
        entities.extend(
            EnvoyStorageCTPhaseEntity(coordinator, description)
            for use_phase, phase in phase_data.items()
            for description in CT_STORAGE_PHASE_SENSORS[use_phase]
            if phase.measurement_type == CtType.STORAGE
        )

    if envoy_data.inverters:
        entities.extend(
            EnvoyInverterEntity(coordinator, description, inverter)
            for description in INVERTER_SENSORS
            for inverter in envoy_data.inverters
        )

    if envoy_data.encharge_inventory:
        entities.extend(
            EnvoyEnchargeInventoryEntity(coordinator, description, encharge)
            for description in ENCHARGE_INVENTORY_SENSORS
            for encharge in envoy_data.encharge_inventory
        )
    if envoy_data.encharge_power:
        entities.extend(
            EnvoyEnchargePowerEntity(coordinator, description, encharge)
            for description in ENCHARGE_POWER_SENSORS
            for encharge in envoy_data.encharge_power
        )
    if envoy_data.encharge_aggregate:
        entities.extend(
            EnvoyEnchargeAggregateEntity(coordinator, description)
            for description in ENCHARGE_AGGREGATE_SENSORS
        )
    if envoy_data.enpower:
        entities.extend(
            EnvoyEnpowerEntity(coordinator, description)
            for description in ENPOWER_SENSORS
        )

    async_add_entities(entities)


class EnvoySensorBaseEntity(EnvoyBaseEntity, SensorEntity):
    """Defines a base envoy entity."""


class EnvoySystemSensorEntity(EnvoySensorBaseEntity):
    """Envoy system base entity."""

    _attr_icon = ICON

    def __init__(
        self,
        coordinator: EnphaseUpdateCoordinator,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize Envoy entity."""
        super().__init__(coordinator, description)
        self._attr_unique_id = f"{self.envoy_serial_num}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self.envoy_serial_num)},
            manufacturer="Enphase",
            model=coordinator.envoy.envoy_model,
            name=coordinator.name,
            sw_version=str(coordinator.envoy.firmware),
            hw_version=coordinator.envoy.part_number,
            serial_number=self.envoy_serial_num,
        )


class EnvoyProductionEntity(EnvoySystemSensorEntity):
    """Envoy production entity."""

    entity_description: EnvoyProductionSensorEntityDescription

    @property
    def native_value(self) -> int | None:
        """Return the state of the sensor."""
        system_production = self.data.system_production
        assert system_production is not None
        return self.entity_description.value_fn(system_production)


class EnvoyConsumptionEntity(EnvoySystemSensorEntity):
    """Envoy consumption entity."""

    entity_description: EnvoyConsumptionSensorEntityDescription

    @property
    def native_value(self) -> int | None:
        """Return the state of the sensor."""
        system_consumption = self.data.system_consumption
        assert system_consumption is not None
        return self.entity_description.value_fn(system_consumption)


class EnvoyProductionPhaseEntity(EnvoySystemSensorEntity):
    """Envoy phase production entity."""

    entity_description: EnvoyProductionSensorEntityDescription

    @property
    def native_value(self) -> int | None:
        """Return the state of the sensor."""
        if TYPE_CHECKING:
            assert self.entity_description.on_phase
            assert self.data.system_production_phases

        if (
            system_production := self.data.system_production_phases[
                self.entity_description.on_phase
            ]
        ) is None:
            return None
        return self.entity_description.value_fn(system_production)


class EnvoyConsumptionPhaseEntity(EnvoySystemSensorEntity):
    """Envoy phase consumption entity."""

    entity_description: EnvoyConsumptionSensorEntityDescription

    @property
    def native_value(self) -> int | None:
        """Return the state of the sensor."""
        if TYPE_CHECKING:
            assert self.entity_description.on_phase
            assert self.data.system_consumption_phases

        if (
            system_consumption := self.data.system_consumption_phases[
                self.entity_description.on_phase
            ]
        ) is None:
            return None
        return self.entity_description.value_fn(system_consumption)


class EnvoyConsumptionCTEntity(EnvoySystemSensorEntity):
    """Envoy net consumption CT entity."""

    entity_description: EnvoyCTSensorEntityDescription

    @property
    def native_value(
        self,
    ) -> int | float | str | CtType | CtMeterStatus | CtStatusFlags | None:
        """Return the state of the CT sensor."""
        if (ctmeter := self.data.ctmeter_consumption) is None:
            return None
        return self.entity_description.value_fn(ctmeter)


class EnvoyConsumptionCTPhaseEntity(EnvoySystemSensorEntity):
    """Envoy net consumption CT phase entity."""

    entity_description: EnvoyCTSensorEntityDescription

    @property
    def native_value(
        self,
    ) -> int | float | str | CtType | CtMeterStatus | CtStatusFlags | None:
        """Return the state of the CT phase sensor."""
        if TYPE_CHECKING:
            assert self.entity_description.on_phase
        if (ctmeter := self.data.ctmeter_consumption_phases) is None:
            return None
        return self.entity_description.value_fn(
            ctmeter[self.entity_description.on_phase]
        )


class EnvoyProductionCTEntity(EnvoySystemSensorEntity):
    """Envoy net consumption CT entity."""

    entity_description: EnvoyCTSensorEntityDescription

    @property
    def native_value(
        self,
    ) -> int | float | str | CtType | CtMeterStatus | CtStatusFlags | None:
        """Return the state of the CT sensor."""
        if (ctmeter := self.data.ctmeter_production) is None:
            return None
        return self.entity_description.value_fn(ctmeter)


class EnvoyProductionCTPhaseEntity(EnvoySystemSensorEntity):
    """Envoy net consumption CT phase entity."""

    entity_description: EnvoyCTSensorEntityDescription

    @property
    def native_value(
        self,
    ) -> int | float | str | CtType | CtMeterStatus | CtStatusFlags | None:
        """Return the state of the CT phase sensor."""
        if TYPE_CHECKING:
            assert self.entity_description.on_phase
        if (ctmeter := self.data.ctmeter_production_phases) is None:
            return None
        return self.entity_description.value_fn(
            ctmeter[self.entity_description.on_phase]
        )


class EnvoyStorageCTEntity(EnvoySystemSensorEntity):
    """Envoy net storage CT entity."""

    entity_description: EnvoyCTSensorEntityDescription

    @property
    def native_value(
        self,
    ) -> int | float | str | CtType | CtMeterStatus | CtStatusFlags | None:
        """Return the state of the CT sensor."""
        if (ctmeter := self.data.ctmeter_storage) is None:
            return None
        return self.entity_description.value_fn(ctmeter)


class EnvoyStorageCTPhaseEntity(EnvoySystemSensorEntity):
    """Envoy net storage CT phase entity."""

    entity_description: EnvoyCTSensorEntityDescription

    @property
    def native_value(
        self,
    ) -> int | float | str | CtType | CtMeterStatus | CtStatusFlags | None:
        """Return the state of the CT phase sensor."""
        if TYPE_CHECKING:
            assert self.entity_description.on_phase
        if (ctmeter := self.data.ctmeter_storage_phases) is None:
            return None
        return self.entity_description.value_fn(
            ctmeter[self.entity_description.on_phase]
        )


class EnvoyInverterEntity(EnvoySensorBaseEntity):
    """Envoy inverter entity."""

    _attr_icon = ICON
    entity_description: EnvoyInverterSensorEntityDescription

    def __init__(
        self,
        coordinator: EnphaseUpdateCoordinator,
        description: EnvoyInverterSensorEntityDescription,
        serial_number: str,
    ) -> None:
        """Initialize Envoy inverter entity."""
        super().__init__(coordinator, description)
        self._serial_number = serial_number
        key = description.key
        if key == INVERTERS_KEY:
            # Originally there was only one inverter sensor, so we don't want to
            # break existing installations by changing the unique_id.
            self._attr_unique_id = serial_number
        else:
            # Additional sensors have a unique_id that includes the
            # sensor key.
            self._attr_unique_id = f"{serial_number}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, serial_number)},
            name=f"Inverter {serial_number}",
            manufacturer="Enphase",
            model="Inverter",
            via_device=(DOMAIN, self.envoy_serial_num),
        )

    @property
    def native_value(self) -> datetime.datetime | float | None:
        """Return the state of the sensor."""
        inverters = self.data.inverters
        assert inverters is not None
        # Some envoy fw versions return an empty inverter array every 4 hours when
        # no production is taking place. Prevent collection failure due to this
        # as other data seems fine. Inverters will show unknown during this cycle.
        if self._serial_number not in inverters:
            _LOGGER.debug(
                "Inverter %s not in returned inverters array (size: %s)",
                self._serial_number,
                len(inverters),
            )
            return None
        return self.entity_description.value_fn(inverters[self._serial_number])


class EnvoyEnchargeEntity(EnvoySensorBaseEntity):
    """Envoy Encharge sensor entity."""

    def __init__(
        self,
        coordinator: EnphaseUpdateCoordinator,
        description: EnvoyEnchargeSensorEntityDescription
        | EnvoyEnchargePowerSensorEntityDescription,
        serial_number: str,
    ) -> None:
        """Initialize Encharge entity."""
        super().__init__(coordinator, description)
        self._serial_number = serial_number
        self._attr_unique_id = f"{serial_number}_{description.key}"
        encharge_inventory = self.data.encharge_inventory
        assert encharge_inventory is not None
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, serial_number)},
            manufacturer="Enphase",
            model="Encharge",
            name=f"Encharge {serial_number}",
            sw_version=str(encharge_inventory[self._serial_number].firmware_version),
            via_device=(DOMAIN, self.envoy_serial_num),
        )


class EnvoyEnchargeInventoryEntity(EnvoyEnchargeEntity):
    """Envoy Encharge inventory entity."""

    entity_description: EnvoyEnchargeSensorEntityDescription

    @property
    def native_value(self) -> int | float | datetime.datetime | None:
        """Return the state of the inventory sensors."""
        encharge_inventory = self.data.encharge_inventory
        assert encharge_inventory is not None
        return self.entity_description.value_fn(encharge_inventory[self._serial_number])


class EnvoyEnchargePowerEntity(EnvoyEnchargeEntity):
    """Envoy Encharge power entity."""

    entity_description: EnvoyEnchargePowerSensorEntityDescription

    @property
    def native_value(self) -> int | float | None:
        """Return the state of the power sensors."""
        encharge_power = self.data.encharge_power
        assert encharge_power is not None
        return self.entity_description.value_fn(encharge_power[self._serial_number])


class EnvoyEnchargeAggregateEntity(EnvoySystemSensorEntity):
    """Envoy Encharge Aggregate sensor entity."""

    entity_description: EnvoyEnchargeAggregateSensorEntityDescription

    @property
    def native_value(self) -> int:
        """Return the state of the aggregate sensors."""
        encharge_aggregate = self.data.encharge_aggregate
        assert encharge_aggregate is not None
        return self.entity_description.value_fn(encharge_aggregate)


class EnvoyEnpowerEntity(EnvoySensorBaseEntity):
    """Envoy Enpower sensor entity."""

    entity_description: EnvoyEnpowerSensorEntityDescription

    def __init__(
        self,
        coordinator: EnphaseUpdateCoordinator,
        description: EnvoyEnpowerSensorEntityDescription,
    ) -> None:
        """Initialize Enpower entity."""
        super().__init__(coordinator, description)
        enpower_data = self.data.enpower
        assert enpower_data is not None
        self._attr_unique_id = f"{enpower_data.serial_number}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, enpower_data.serial_number)},
            manufacturer="Enphase",
            model="Enpower",
            name=f"Enpower {enpower_data.serial_number}",
            sw_version=str(enpower_data.firmware_version),
            via_device=(DOMAIN, self.envoy_serial_num),
        )

    @property
    def native_value(self) -> datetime.datetime | int | float | None:
        """Return the state of the power sensors."""
        enpower = self.data.enpower
        assert enpower is not None
        return self.entity_description.value_fn(enpower)
