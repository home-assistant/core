"""Sensor platform for the GridX integration."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

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
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .coordinator import (
    GridxHistoricalCoordinator,
    GridxHistoricalData,
    GridxLiveCoordinator,
)
from .types import GridxConfigEntry

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class GridxSensorEntityDescription(SensorEntityDescription):
    """Extends SensorEntityDescription with a value extractor function."""

    value_fn: Callable[[Mapping[str, Any]], StateType | None]
    coordinator_type: Literal["live", "hist"] = "live"


# ---------------------------------------------------------------------------
# Live — base sensors
# ---------------------------------------------------------------------------
LIVE_BASE_DESCRIPTIONS: tuple[GridxSensorEntityDescription, ...] = (
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
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: (
            round(float(d["directConsumptionRate"]) * 100, 2)
            if d.get("directConsumptionRate") is not None
            else None
        ),
    ),
    GridxSensorEntityDescription(
        key="selfConsumptionRate",
        translation_key="self_consumption_rate",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: (
            round(float(d["selfConsumptionRate"]) * 100, 2)
            if d.get("selfConsumptionRate") is not None
            else None
        ),
    ),
    GridxSensorEntityDescription(
        key="selfSufficiencyRate",
        translation_key="self_sufficiency_rate",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: (
            round(float(d["selfSufficiencyRate"]) * 100, 2)
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
        value_fn=lambda d: (
            round(d["gridMeterReadingPositive"] / 3600, 2)
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
        value_fn=lambda d: (
            round(d["gridMeterReadingNegative"] / 3600, 2)
            if d.get("gridMeterReadingNegative") is not None
            else None
        ),
    ),
)

# ---------------------------------------------------------------------------
# Live — battery sensors (optional, None when no battery present)
# ---------------------------------------------------------------------------
LIVE_BATTERY_DESCRIPTIONS: tuple[GridxSensorEntityDescription, ...] = (
    GridxSensorEntityDescription(
        key="battery_stateOfCharge",
        translation_key="battery_state_of_charge",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: (
            round(float(d["battery"]["stateOfCharge"]) * 100, 1)
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

# ---------------------------------------------------------------------------
# Live — EV charging station sensors (optional)
# ---------------------------------------------------------------------------
LIVE_EV_DESCRIPTIONS: tuple[GridxSensorEntityDescription, ...] = (
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
        value_fn=lambda d: (
            round(float(d["evChargingStation"]["stateOfCharge"]) * 100, 1)
            if d.get("evChargingStation")
            and d["evChargingStation"].get("stateOfCharge") is not None
            else None
        ),
    ),
    GridxSensorEntityDescription(
        key="ev_currentL1",
        translation_key="ev_current_l1",
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
        translation_key="ev_current_l2",
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
        translation_key="ev_current_l3",
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

# ---------------------------------------------------------------------------
# Live — heat pump sensors (optional)
# ---------------------------------------------------------------------------
LIVE_HEATPUMP_DESCRIPTIONS: tuple[GridxSensorEntityDescription, ...] = (
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

# ---------------------------------------------------------------------------
# Live — heater sensors (optional)
# ---------------------------------------------------------------------------
LIVE_HEATER_DESCRIPTIONS: tuple[GridxSensorEntityDescription, ...] = (
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

# ---------------------------------------------------------------------------
# Historical — daily energy totals
# ---------------------------------------------------------------------------
HIST_BASE_DESCRIPTIONS: tuple[GridxSensorEntityDescription, ...] = (
    GridxSensorEntityDescription(
        key="hist_photovoltaic",
        translation_key="hist_photovoltaic",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        coordinator_type="hist",
        value_fn=lambda d: d["total"].get("photovoltaic"),
    ),
    GridxSensorEntityDescription(
        key="hist_consumption",
        translation_key="hist_consumption",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        coordinator_type="hist",
        value_fn=lambda d: d["total"].get("consumption"),
    ),
    GridxSensorEntityDescription(
        key="hist_production",
        translation_key="hist_production",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        coordinator_type="hist",
        value_fn=lambda d: d["total"].get("production"),
    ),
    GridxSensorEntityDescription(
        key="hist_feedIn",
        translation_key="hist_feed_in",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        coordinator_type="hist",
        value_fn=lambda d: d["total"].get("feedIn"),
    ),
    GridxSensorEntityDescription(
        key="hist_supply",
        translation_key="hist_supply",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        coordinator_type="hist",
        value_fn=lambda d: d["total"].get("supply"),
    ),
    GridxSensorEntityDescription(
        key="hist_selfConsumption",
        translation_key="hist_self_consumption",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        coordinator_type="hist",
        value_fn=lambda d: d["total"].get("selfConsumption"),
    ),
    GridxSensorEntityDescription(
        key="hist_selfSupply",
        translation_key="hist_self_supply",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        coordinator_type="hist",
        value_fn=lambda d: d["total"].get("selfSupply"),
    ),
    GridxSensorEntityDescription(
        key="hist_totalConsumption",
        translation_key="hist_total_consumption",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        coordinator_type="hist",
        value_fn=lambda d: d["total"].get("totalConsumption"),
    ),
    GridxSensorEntityDescription(
        key="hist_directConsumptionHousehold",
        translation_key="hist_direct_consumption_household",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        coordinator_type="hist",
        value_fn=lambda d: d["total"].get("directConsumptionHousehold"),
    ),
    GridxSensorEntityDescription(
        key="hist_directConsumptionHeatPump",
        translation_key="hist_direct_consumption_heat_pump",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        coordinator_type="hist",
        entity_registry_enabled_default=False,
        value_fn=lambda d: d["total"].get("directConsumptionHeatPump"),
    ),
    GridxSensorEntityDescription(
        key="hist_directConsumptionEV",
        translation_key="hist_direct_consumption_ev",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        coordinator_type="hist",
        entity_registry_enabled_default=False,
        value_fn=lambda d: d["total"].get("directConsumptionEV"),
    ),
    GridxSensorEntityDescription(
        key="hist_directConsumptionHeater",
        translation_key="hist_direct_consumption_heater",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        coordinator_type="hist",
        entity_registry_enabled_default=False,
        value_fn=lambda d: d["total"].get("directConsumptionHeater"),
    ),
    GridxSensorEntityDescription(
        key="hist_selfConsumptionRate",
        translation_key="hist_self_consumption_rate",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
        coordinator_type="hist",
        value_fn=lambda d: (
            round(float(d["total"]["selfConsumptionRate"]) * 100, 2)
            if d["total"].get("selfConsumptionRate") is not None
            else None
        ),
    ),
    GridxSensorEntityDescription(
        key="hist_selfSufficiencyRate",
        translation_key="hist_self_sufficiency_rate",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
        coordinator_type="hist",
        value_fn=lambda d: (
            round(float(d["total"]["selfSufficiencyRate"]) * 100, 2)
            if d["total"].get("selfSufficiencyRate") is not None
            else None
        ),
    ),
)

ALL_DESCRIPTIONS: tuple[GridxSensorEntityDescription, ...] = (
    *LIVE_BASE_DESCRIPTIONS,
    *LIVE_BATTERY_DESCRIPTIONS,
    *LIVE_EV_DESCRIPTIONS,
    *LIVE_HEATPUMP_DESCRIPTIONS,
    *LIVE_HEATER_DESCRIPTIONS,
    *HIST_BASE_DESCRIPTIONS,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GridxConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up GridX sensor entities from a config entry."""
    live_coordinator = entry.runtime_data.live_coordinator
    hist_coordinator = entry.runtime_data.hist_coordinator

    entities: list[SensorEntity] = []
    for description in ALL_DESCRIPTIONS:
        if description.coordinator_type == "hist":
            entities.append(
                GridxHistoricalSensorEntity(
                    coordinator=hist_coordinator,
                    description=description,
                    entry=entry,
                )
            )
            continue

        entities.append(
            GridxLiveSensorEntity(
                coordinator=live_coordinator,
                description=description,
                entry=entry,
            )
        )

    async_add_entities(entities)


class GridxLiveSensorEntity(CoordinatorEntity[GridxLiveCoordinator], SensorEntity):
    """A GridX live sensor entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: GridxLiveCoordinator,
        description: GridxSensorEntityDescription,
        entry: GridxConfigEntry,
    ) -> None:
        """Initialize the live sensor."""
        super().__init__(coordinator)
        self.entity_description: GridxSensorEntityDescription = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="GridX GridBox",
            manufacturer="gridX / Viessmann",
            model="GridBox",
        )

    @property
    def native_value(self) -> StateType | None:
        """Return the sensor value by calling the description's value_fn."""
        try:
            return self.entity_description.value_fn(self.coordinator.data)
        except (KeyError, TypeError, ValueError):
            return None


class GridxHistoricalSensorEntity(
    CoordinatorEntity[GridxHistoricalCoordinator], SensorEntity
):
    """A GridX historical sensor entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: GridxHistoricalCoordinator,
        description: GridxSensorEntityDescription,
        entry: GridxConfigEntry,
    ) -> None:
        """Initialize the historical sensor."""
        super().__init__(coordinator)
        self.entity_description: GridxSensorEntityDescription = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="GridX GridBox",
            manufacturer="gridX / Viessmann",
            model="GridBox",
        )

    @property
    def native_value(self) -> StateType | None:
        """Return the sensor value by calling the description's value_fn."""
        try:
            return self.entity_description.value_fn(self.coordinator.data)
        except (KeyError, TypeError, ValueError):
            return None

    @property
    def last_reset(self) -> datetime | None:
        """Return last_reset for TOTAL state-class historical sensors."""
        if self.entity_description.state_class != SensorStateClass.TOTAL:
            return None
        data: GridxHistoricalData = self.coordinator.data
        if not data:
            return None
        try:
            return dt_util.parse_datetime(data["last_reset"])
        except (KeyError, ValueError):
            return None
