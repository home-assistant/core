"""Sensor platform for the GridX integration."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, override

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    UnitOfElectricCurrent,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import GridxLiveCoordinator
from .types import GridxConfigEntry

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class GridxSensorEntityDescription(SensorEntityDescription):
    """Extends SensorEntityDescription with a value extractor function."""

    value_fn: Callable[[Mapping[str, Any]], StateType | None]
    translation_placeholders: dict[str, str] | None = None


BASE_DESCRIPTIONS: tuple[GridxSensorEntityDescription, ...] = (
    GridxSensorEntityDescription(
        key="photovoltaic",
        translation_key="photovoltaic",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.get("photovoltaic"),
    ),
    GridxSensorEntityDescription(
        key="consumption",
        translation_key="consumption",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.get("consumption"),
    ),
    GridxSensorEntityDescription(
        key="grid",
        translation_key="grid",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.get("grid"),
    ),
    GridxSensorEntityDescription(
        key="production",
        translation_key="production",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.get("production"),
    ),
    GridxSensorEntityDescription(
        key="selfConsumption",
        translation_key="self_consumption",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.get("selfConsumption"),
    ),
    GridxSensorEntityDescription(
        key="selfSupply",
        translation_key="self_supply",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.get("selfSupply"),
    ),
    GridxSensorEntityDescription(
        key="totalConsumption",
        translation_key="total_consumption",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.get("totalConsumption"),
    ),
    GridxSensorEntityDescription(
        key="directConsumptionHousehold",
        translation_key="direct_consumption_household",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.get("directConsumptionHousehold"),
    ),
    GridxSensorEntityDescription(
        key="directConsumptionHeatPump",
        translation_key="direct_consumption_heat_pump",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda d: d.get("directConsumptionHeatPump"),
    ),
    GridxSensorEntityDescription(
        key="directConsumptionEV",
        translation_key="direct_consumption_ev",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda d: d.get("directConsumptionEV"),
    ),
    GridxSensorEntityDescription(
        key="directConsumptionHeater",
        translation_key="direct_consumption_heater",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda d: d.get("directConsumptionHeater"),
    ),
    GridxSensorEntityDescription(
        key="directConsumptionRate",
        translation_key="direct_consumption_rate",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda d: (
            float(d["directConsumptionRate"]) * 100
            if d.get("directConsumptionRate") is not None
            else None
        ),
    ),
    GridxSensorEntityDescription(
        key="selfConsumptionRate",
        translation_key="self_consumption_rate",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda d: (
            float(d["selfConsumptionRate"]) * 100
            if d.get("selfConsumptionRate") is not None
            else None
        ),
    ),
    GridxSensorEntityDescription(
        key="selfSufficiencyRate",
        translation_key="self_sufficiency_rate",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda d: (
            float(d["selfSufficiencyRate"]) * 100
            if d.get("selfSufficiencyRate") is not None
            else None
        ),
    ),
    # Grid meter readings: API returns Ws (watt-seconds) — convert to Wh
    GridxSensorEntityDescription(
        key="gridMeterReadingPositive",
        translation_key="grid_meter_reading_positive",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
        value_fn=lambda d: (
            d["gridMeterReadingPositive"] / 3600
            if d.get("gridMeterReadingPositive") is not None
            else None
        ),
    ),
    GridxSensorEntityDescription(
        key="gridMeterReadingNegative",
        translation_key="grid_meter_reading_negative",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
        value_fn=lambda d: (
            d["gridMeterReadingNegative"] / 3600
            if d.get("gridMeterReadingNegative") is not None
            else None
        ),
    ),
)

BATTERY_DESCRIPTIONS: tuple[GridxSensorEntityDescription, ...] = (
    GridxSensorEntityDescription(
        key="battery_stateOfCharge",
        translation_key="battery_state_of_charge",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda d: (
            float(d["battery"]["stateOfCharge"]) * 100
            if d.get("battery") and d["battery"].get("stateOfCharge") is not None
            else None
        ),
    ),
    GridxSensorEntityDescription(
        key="battery_power",
        translation_key="battery_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d["battery"].get("power") if d.get("battery") else None,
    ),
    GridxSensorEntityDescription(
        key="battery_capacity",
        translation_key="battery_capacity",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY_STORAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda d: d["battery"].get("capacity") if d.get("battery") else None,
    ),
    GridxSensorEntityDescription(
        key="battery_remainingCharge",
        translation_key="battery_remaining_charge",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY_STORAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: (
            d["battery"].get("remainingCharge") if d.get("battery") else None
        ),
    ),
    GridxSensorEntityDescription(
        key="battery_charge",
        translation_key="battery_charge",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY_STORAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda d: d["battery"].get("charge") if d.get("battery") else None,
    ),
    GridxSensorEntityDescription(
        key="battery_discharge",
        translation_key="battery_discharge",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY_STORAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda d: d["battery"].get("discharge") if d.get("battery") else None,
    ),
)

EV_DESCRIPTIONS: tuple[GridxSensorEntityDescription, ...] = (
    GridxSensorEntityDescription(
        key="ev_power",
        translation_key="ev_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda d: (
            d["evChargingStation"].get("power") if d.get("evChargingStation") else None
        ),
    ),
    GridxSensorEntityDescription(
        key="ev_stateOfCharge",
        translation_key="ev_state_of_charge",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        suggested_display_precision=1,
        value_fn=lambda d: (
            float(d["evChargingStation"]["stateOfCharge"]) * 100
            if d.get("evChargingStation")
            and d["evChargingStation"].get("stateOfCharge") is not None
            else None
        ),
    ),
    GridxSensorEntityDescription(
        key="ev_currentL1",
        translation_key="ev_current_phase",
        translation_placeholders={"phase": "L1"},
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda d: (
            d["evChargingStation"].get("currentL1")
            if d.get("evChargingStation")
            else None
        ),
    ),
    GridxSensorEntityDescription(
        key="ev_currentL2",
        translation_key="ev_current_phase",
        translation_placeholders={"phase": "L2"},
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda d: (
            d["evChargingStation"].get("currentL2")
            if d.get("evChargingStation")
            else None
        ),
    ),
    GridxSensorEntityDescription(
        key="ev_currentL3",
        translation_key="ev_current_phase",
        translation_placeholders={"phase": "L3"},
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda d: (
            d["evChargingStation"].get("currentL3")
            if d.get("evChargingStation")
            else None
        ),
    ),
    GridxSensorEntityDescription(
        key="ev_readingTotal",
        translation_key="ev_reading_total",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
        value_fn=lambda d: (
            d["evChargingStation"].get("readingTotal")
            if d.get("evChargingStation")
            else None
        ),
    ),
)

HEATPUMP_DESCRIPTIONS: tuple[GridxSensorEntityDescription, ...] = (
    GridxSensorEntityDescription(
        key="heatpump_power",
        translation_key="heatpump_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda d: (d.get("heatPumps") or [{}])[0].get("power"),
    ),
)

HEATER_DESCRIPTIONS: tuple[GridxSensorEntityDescription, ...] = (
    GridxSensorEntityDescription(
        key="heater_power",
        translation_key="heater_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda d: (d.get("heaters") or [{}])[0].get("power"),
    ),
    GridxSensorEntityDescription(
        key="heater_temperature",
        translation_key="heater_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda d: (d.get("heaters") or [{}])[0].get("temperature"),
    ),
)

# Optional subsystem sensors are only created when the corresponding data is
# present in the live payload, keyed by the payload field to check.
OPTIONAL_DESCRIPTIONS: tuple[
    tuple[str, tuple[GridxSensorEntityDescription, ...]], ...
] = (
    ("battery", BATTERY_DESCRIPTIONS),
    ("evChargingStation", EV_DESCRIPTIONS),
    ("heatPumps", HEATPUMP_DESCRIPTIONS),
    ("heaters", HEATER_DESCRIPTIONS),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GridxConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up GridX sensor entities from a config entry."""
    coordinator = entry.runtime_data.coordinator

    descriptions = [*BASE_DESCRIPTIONS]
    live_data = coordinator.data or {}
    for data_key, optional_descriptions in OPTIONAL_DESCRIPTIONS:
        if live_data.get(data_key):
            descriptions.extend(optional_descriptions)

    async_add_entities(
        GridxSensorEntity(
            coordinator=coordinator,
            description=description,
            entry=entry,
        )
        for description in descriptions
    )


class GridxSensorEntity(CoordinatorEntity[GridxLiveCoordinator], SensorEntity):
    """A GridX sensor entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: GridxLiveCoordinator,
        description: GridxSensorEntityDescription,
        entry: GridxConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description: GridxSensorEntityDescription = description
        self._attr_unique_id = f"{entry.unique_id}_{description.key}"
        if description.translation_placeholders:
            self._attr_translation_placeholders = description.translation_placeholders
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(entry.unique_id))},
            name="GridX GridBox",
            manufacturer="gridX / Viessmann",
            model="GridBox",
        )

    @property
    @override
    def native_value(self) -> StateType | None:
        """Return the sensor value by calling the description's value_fn."""
        try:
            return self.entity_description.value_fn(self.coordinator.data)
        except KeyError, TypeError, ValueError:
            return None
