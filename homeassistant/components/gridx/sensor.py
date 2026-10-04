"""Sensor platform for the gridX integration."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, override

from gridx_connector import GridXSystem

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
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .coordinator import GridxConfigEntry, GridxLiveCoordinator
from .entity import GridxEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class GridxSensorEntityDescription(SensorEntityDescription):
    """Describes a gridX sensor."""

    value_fn: Callable[[Mapping[str, Any]], StateType]
    # Payload key that must be present for the sensor to be created, for
    # sensors of optional subsystems (battery, EV charger, heat pump, heater).
    subsystem_key: str | None = None


def _power(
    key: str, payload_key: str, *, enabled: bool = True
) -> GridxSensorEntityDescription:
    """Describe a power sensor reading ``payload_key`` from the live data."""
    return GridxSensorEntityDescription(
        key=key,
        translation_key=key,
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        entity_registry_enabled_default=enabled,
        value_fn=lambda d: d.get(payload_key),
    )


def _rate(key: str, payload_key: str) -> GridxSensorEntityDescription:
    """Describe a ratio (0..1) sensor shown as a percentage."""
    return GridxSensorEntityDescription(
        key=key,
        translation_key=key,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda d: (
            float(d[payload_key]) * 100 if d.get(payload_key) is not None else None
        ),
    )


def _battery(key: str) -> Callable[[Mapping[str, Any]], StateType]:
    return lambda d: (d.get("battery") or {}).get(key)


def _ev(key: str) -> Callable[[Mapping[str, Any]], StateType]:
    return lambda d: (d.get("evChargingStation") or {}).get(key)


SENSOR_DESCRIPTIONS: tuple[GridxSensorEntityDescription, ...] = (
    _power("photovoltaic", "photovoltaic"),
    _power("consumption", "consumption"),
    _power("grid", "grid"),
    _power("production", "production"),
    _power("self_consumption", "selfConsumption"),
    _power("self_supply", "selfSupply"),
    _power("total_consumption", "totalConsumption"),
    _power("direct_consumption_household", "directConsumptionHousehold"),
    _power("direct_consumption_heat_pump", "directConsumptionHeatPump", enabled=False),
    _power("direct_consumption_ev", "directConsumptionEV", enabled=False),
    _power("direct_consumption_heater", "directConsumptionHeater", enabled=False),
    _rate("direct_consumption_rate", "directConsumptionRate"),
    _rate("self_consumption_rate", "selfConsumptionRate"),
    _rate("self_sufficiency_rate", "selfSufficiencyRate"),
    # Grid meter readings are reported in Ws; convert to Wh.
    GridxSensorEntityDescription(
        key="grid_meter_reading_positive",
        translation_key="grid_meter_reading_positive",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=1,
        value_fn=lambda d: (
            d["gridMeterReadingPositive"] / 3600
            if d.get("gridMeterReadingPositive") is not None
            else None
        ),
    ),
    GridxSensorEntityDescription(
        key="grid_meter_reading_negative",
        translation_key="grid_meter_reading_negative",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=1,
        value_fn=lambda d: (
            d["gridMeterReadingNegative"] / 3600
            if d.get("gridMeterReadingNegative") is not None
            else None
        ),
    ),
    GridxSensorEntityDescription(
        key="battery_state_of_charge",
        translation_key="battery_state_of_charge",
        subsystem_key="battery",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda d: (
            float(soc) * 100
            if (soc := (d.get("battery") or {}).get("stateOfCharge")) is not None
            else None
        ),
    ),
    # Positive values mean discharging, negative values charging (API convention).
    GridxSensorEntityDescription(
        key="battery_power",
        translation_key="battery_power",
        subsystem_key="battery",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=_battery("power"),
    ),
    GridxSensorEntityDescription(
        key="battery_capacity",
        translation_key="battery_capacity",
        subsystem_key="battery",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY_STORAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=_battery("capacity"),
    ),
    GridxSensorEntityDescription(
        key="battery_remaining_charge",
        translation_key="battery_remaining_charge",
        subsystem_key="battery",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY_STORAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_battery("remainingCharge"),
    ),
    GridxSensorEntityDescription(
        key="ev_power",
        translation_key="ev_power",
        subsystem_key="evChargingStation",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=_ev("power"),
    ),
    GridxSensorEntityDescription(
        key="ev_state_of_charge",
        translation_key="ev_state_of_charge",
        subsystem_key="evChargingStation",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda d: (
            float(soc) * 100
            if (soc := (d.get("evChargingStation") or {}).get("stateOfCharge"))
            is not None
            else None
        ),
    ),
    *(
        GridxSensorEntityDescription(
            key=f"ev_current_l{phase}",
            translation_key="ev_current_phase",
            translation_placeholders={"phase": f"L{phase}"},
            subsystem_key="evChargingStation",
            native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
            device_class=SensorDeviceClass.CURRENT,
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=False,
            value_fn=_ev(f"currentL{phase}"),  # codespell:ignore currentl
        )
        for phase in (1, 2, 3)
    ),
    GridxSensorEntityDescription(
        key="ev_reading_total",
        translation_key="ev_reading_total",
        subsystem_key="evChargingStation",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=1,
        value_fn=_ev("readingTotal"),
    ),
    # Heat pump and heaters: the API provides aggregated values.
    GridxSensorEntityDescription(
        key="heatpump_power",
        translation_key="heatpump_power",
        subsystem_key="heatPump",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda d: d.get("heatPump"),
    ),
    GridxSensorEntityDescription(
        key="heater_power",
        translation_key="heater_power",
        subsystem_key="heating",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda d: d.get("heating"),
    ),
    GridxSensorEntityDescription(
        key="heater_temperature",
        translation_key="heater_temperature",
        subsystem_key="heatingTemperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda d: d.get("heatingTemperature"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GridxConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up gridX sensors for every system of the account."""
    coordinator = entry.runtime_data
    known: set[tuple[str, str]] = set()

    @callback
    def _add_new_entities() -> None:
        """Add sensors for subsystems that appear in the live data."""
        new_entities = [
            GridxSensorEntity(coordinator, coordinator.systems[system_id], description)
            for system_id, live_data in coordinator.data.items()
            for description in SENSOR_DESCRIPTIONS
            if (system_id, description.key) not in known
            and (
                description.subsystem_key is None
                or live_data.get(description.subsystem_key) is not None
            )
        ]
        known.update(
            (entity.system_id, entity.entity_description.key) for entity in new_entities
        )
        async_add_entities(new_entities)

    _add_new_entities()
    entry.async_on_unload(coordinator.async_add_listener(_add_new_entities))


class GridxSensorEntity(GridxEntity, SensorEntity):
    """A gridX sensor."""

    entity_description: GridxSensorEntityDescription

    def __init__(
        self,
        coordinator: GridxLiveCoordinator,
        system: GridXSystem,
        description: GridxSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, system)
        self.entity_description = description
        self._attr_unique_id = f"{system.id}_{description.key}"

    @property
    @override
    def native_value(self) -> StateType:
        """Return the sensor value."""
        return self.entity_description.value_fn(self.coordinator.data[self.system_id])
