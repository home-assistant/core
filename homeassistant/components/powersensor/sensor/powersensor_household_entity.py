"""Wrapper around powersensor_local.VirtualHousehold for smooth interface with Homeassistant energy view."""

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum

from powersensor_local import VirtualHousehold

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfEnergy, UnitOfPower
from homeassistant.helpers.device_registry import DeviceInfo

from ..const import DOMAIN


class HouseholdMeasurements(Enum):
    """Measurements for Household Entity."""

    POWER_HOME_USE = 1
    POWER_FROM_GRID = 2
    POWER_TO_GRID = 3
    POWER_SOLAR_GENERATION = 4
    ENERGY_HOME_USE = 5
    ENERGY_FROM_GRID = 6
    ENERGY_TO_GRID = 7
    ENERGY_SOLAR_GENERATION = 8


ConsumptionMeasurements = [
    HouseholdMeasurements.POWER_HOME_USE,
    HouseholdMeasurements.POWER_FROM_GRID,
    HouseholdMeasurements.ENERGY_HOME_USE,
    HouseholdMeasurements.ENERGY_FROM_GRID,
]
ProductionMeasurements = [
    HouseholdMeasurements.POWER_TO_GRID,
    HouseholdMeasurements.POWER_SOLAR_GENERATION,
    HouseholdMeasurements.ENERGY_TO_GRID,
    HouseholdMeasurements.ENERGY_SOLAR_GENERATION,
]


@dataclass(frozen=True, kw_only=True)
class PowersensorVirtualHouseholdSensorEntityDescription(SensorEntityDescription):
    """Powersensor Virtual Household Sensor Entity Description."""

    formatter: Callable
    event: str


def fmt_int(f):
    """Wrapper to format integers appropriately."""
    return int(f)


def fmt_ws_to_kwh(f):
    """Wrapper convert a watt-seconds string to kilowatt-hours float."""
    return float(f) / 3600000


class PowersensorHouseholdEntity(SensorEntity):
    """Powersensor Virtual Household entity."""

    should_poll = False
    _attr_has_entity_name = True
    _attr_available = True

    _ENTITY_CONFIGS = {
        HouseholdMeasurements.POWER_HOME_USE: PowersensorVirtualHouseholdSensorEntityDescription(
            key="Power - Home use",
            device_class=SensorDeviceClass.POWER,
            native_unit_of_measurement=UnitOfPower.WATT,
            state_class=SensorStateClass.MEASUREMENT,
            suggested_display_precision=0,
            formatter=fmt_int,
            event="home_usage",
        ),
        HouseholdMeasurements.POWER_FROM_GRID: PowersensorVirtualHouseholdSensorEntityDescription(
            key="Power - From grid",
            device_class=SensorDeviceClass.POWER,
            native_unit_of_measurement=UnitOfPower.WATT,
            state_class=SensorStateClass.MEASUREMENT,
            suggested_display_precision=0,
            formatter=fmt_int,
            event="from_grid",
        ),
        HouseholdMeasurements.POWER_TO_GRID: PowersensorVirtualHouseholdSensorEntityDescription(
            key="Power - To grid",
            device_class=SensorDeviceClass.POWER,
            native_unit_of_measurement=UnitOfPower.WATT,
            state_class=SensorStateClass.MEASUREMENT,
            suggested_display_precision=0,
            formatter=fmt_int,
            event="to_grid",
        ),
        HouseholdMeasurements.POWER_SOLAR_GENERATION: PowersensorVirtualHouseholdSensorEntityDescription(
            key="Power - Solar generation",
            device_class=SensorDeviceClass.POWER,
            native_unit_of_measurement=UnitOfPower.WATT,
            state_class=SensorStateClass.MEASUREMENT,
            suggested_display_precision=0,
            formatter=fmt_int,
            event="solar_generation",
        ),
        HouseholdMeasurements.ENERGY_HOME_USE: PowersensorVirtualHouseholdSensorEntityDescription(
            key="Energy - Home usage",
            device_class=SensorDeviceClass.ENERGY,
            native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
            state_class=SensorStateClass.TOTAL_INCREASING,
            suggested_display_precision=3,
            formatter=fmt_ws_to_kwh,
            event="home_usage_summation",
        ),
        HouseholdMeasurements.ENERGY_FROM_GRID: PowersensorVirtualHouseholdSensorEntityDescription(
            key="Energy - From grid",
            device_class=SensorDeviceClass.ENERGY,
            state_class=SensorStateClass.TOTAL_INCREASING,
            native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
            formatter=fmt_ws_to_kwh,
            suggested_display_precision=3,
            event="from_grid_summation",
        ),
        HouseholdMeasurements.ENERGY_TO_GRID: PowersensorVirtualHouseholdSensorEntityDescription(
            key="Energy - To grid",
            device_class=SensorDeviceClass.ENERGY,
            state_class=SensorStateClass.TOTAL_INCREASING,
            native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
            formatter=fmt_ws_to_kwh,
            suggested_display_precision=3,
            event="to_grid_summation",
        ),
        HouseholdMeasurements.ENERGY_SOLAR_GENERATION: PowersensorVirtualHouseholdSensorEntityDescription(
            key="Energy - Solar generation",
            device_class=SensorDeviceClass.ENERGY,
            state_class=SensorStateClass.TOTAL_INCREASING,
            native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
            formatter=fmt_ws_to_kwh,
            suggested_display_precision=3,
            event="solar_generation_summation",
        ),
    }

    def __init__(
        self, vhh: VirtualHousehold, measurement_type: HouseholdMeasurements
    ) -> None:
        """Initialize the entity."""
        self._vhh = vhh
        self._attr_should_poll = False
        self._config = self._ENTITY_CONFIGS[measurement_type]

        self._attr_name = self._config.key
        self._attr_unique_id = f"vhh_{self._config.event}"

        self.entity_description = self._config

    @property
    def device_info(self) -> DeviceInfo:
        """DeviceInfo for Powersensor Virtual Household Entity. Includes mac, name and model."""
        return {
            "identifiers": {(DOMAIN, "vhh")},
            "manufacturer": "Powersensor",
            "model": "Virtual",
            "name": "Powersensor Household View 🏠",
        }

    async def async_added_to_hass(self):
        """When added to Homeassistant, Virtual Household needs to subscribe to the update events."""
        self._vhh.subscribe(self._config.event, self._on_event)

    async def async_will_remove_from_hass(self):
        """When removed to Homeassistant, Virtual Household needs to unsubscribe to the update events."""
        self._vhh.unsubscribe(self._config.event, self._on_event)

    async def _on_event(self, _, msg):
        val = None
        if self._config.native_unit_of_measurement == UnitOfPower.WATT:
            key = "watts"
            if key in msg:
                val = msg[key]
        elif self._config.native_unit_of_measurement == UnitOfEnergy.KILO_WATT_HOUR:
            key = "summation_joules"
            if key in msg:
                val = msg[key]
        if val is not None:
            self._attr_native_value = self._config.formatter(val)
            self.async_write_ha_state()
