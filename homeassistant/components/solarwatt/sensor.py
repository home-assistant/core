"""Solarwatt interface sensors."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)

# from homeassistant.helpers.entity import EntityCategory
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
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import SolarwattConfigEntry
from .const import DOMAIN
from .coordinator import SolarwattDataUpdateCoordinator


@dataclass(frozen=True, kw_only=True)
class SolarwattSensorEntityDescription(SensorEntityDescription):
    """Describes a Solarwatt sensor entity."""

    # JSON path inside the API payload, e.g. ("S", "B", "SOC")
    value_path: tuple[str, ...] | None = None


# Map a few useful values from the JSON spec to HA sensors.
# Example JSON from spec:
# {
#   "S": {
#     "B": {"SOC": 5, "SOH": 99, "BI": 0, "BV": 0, ...},
#     "DC": {"TAMB": 23, ...},
#   },
#   "H": {"HP": 0},
#   "N": {"NP": 0, "NF": 0, ...},
#   ...
# }

SENSOR_ENTITIES: tuple[SolarwattSensorEntityDescription, ...] = (
    SolarwattSensorEntityDescription(
        key="battery_soc",
        name="Battery State of Charge",
        value_path=("S", "B", "SOC"),
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SolarwattSensorEntityDescription(
        key="battery_soh",
        name="Battery State of Health",
        value_path=("S", "B", "SOH"),
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SolarwattSensorEntityDescription(
        key="battery_voltage",
        name="Battery Voltage",
        value_path=("S", "B", "BV"),
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SolarwattSensorEntityDescription(
        key="battery_current",
        name="Battery Current",
        value_path=("S", "B", "BI"),
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SolarwattSensorEntityDescription(
        key="current_out",
        name="Cumulated Current Out",
        value_path=("S", "B", "COUT"),  # [Ah]
        native_unit_of_measurement="Ah",
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SolarwattSensorEntityDescription(
        key="current_in",
        name="Cumulated Current In",
        value_path=("S", "B", "CIN"),  # [Ah]
        native_unit_of_measurement="Ah",
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SolarwattSensorEntityDescription(
        key="energy_out",
        name="Battery Energy Out",
        value_path=("S", "B", "EOUT"),  # [Wh]
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SolarwattSensorEntityDescription(
        key="energy_in",
        name="Battery Energy In",
        value_path=("S", "B", "EIN"),  # [Wh]
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    # --- AC side ---
    SolarwattSensorEntityDescription(
        key="ac_voltage",
        name="AC Voltage",
        value_path=("S", "AC", "ACV"),
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SolarwattSensorEntityDescription(
        key="ac_current",
        name="AC Current",
        value_path=("S", "AC", "ACI"),  # codespell:ignore
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SolarwattSensorEntityDescription(
        key="ac_frequency",
        name="AC Frequency",
        value_path=("S", "AC", "ACF"),
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    # --- DC / PV side ---
    SolarwattSensorEntityDescription(
        key="dc_voltage",
        name="DC Voltage",
        value_path=("S", "DC", "DCV"),
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SolarwattSensorEntityDescription(
        key="dc_power_charge",
        name="DC Power Charge",
        value_path=("S", "DC", "DCPC"),  # [W] laut typischen Specs
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    SolarwattSensorEntityDescription(
        key="dc_power_discharge",
        name="DC Power Discharge",
        value_path=("S", "DC", "DCPD"),  # [W]
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    # --- Home / grid ---
    SolarwattSensorEntityDescription(
        key="home_power",
        name="Home Power",
        value_path=("H", "HP"),
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SolarwattSensorEntityDescription(
        key="grid_power",
        name="Grid Power",
        value_path=("N", "NP"),
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SolarwattSensorEntityDescription(
        key="grid_frequency",
        name="Grid Frequency",
        value_path=("N", "NF"),
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SolarwattSensorEntityDescription(
        key="grid_voltage",
        name="Grid Voltage",
        value_path=("N", "NV"),
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # --- System voltages ---
    SolarwattSensorEntityDescription(
        key="system_voltage",
        name="System Voltage (19V)",
        value_path=("A", "VSYS"),
        native_unit_of_measurement=UnitOfElectricPotential.MILLIVOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SolarwattSensorEntityDescription(
        key="cell_voltage",
        name="Cell Voltage",
        value_path=("A", "VBKP"),
        native_unit_of_measurement=UnitOfElectricPotential.MILLIVOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    # --- Temperatures ---
    SolarwattSensorEntityDescription(
        key="ambient_temperature",
        name="Ambient Temperature",
        value_path=("S", "DC", "TAMB"),
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SolarwattSensorEntityDescription(
        key="cell_temperature",
        name="Cell temperature",
        value_path=("S", "B", "CELL", "TMEAN"),
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # --- Firmware / network (diagnostic) ---
    SolarwattSensorEntityDescription(
        key="firmware_version",
        name="Firmware Version",
        value_path=("C", "V"),
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SolarwattSensorEntityDescription(
        key="hardware_version",
        name="Hardware Version",
        value_path=("C", "HW"),
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SolarwattSensorEntityDescription(
        key="acs_version",
        name="ACS Version",
        value_path=("C", "ACS"),
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SolarwattSensorEntityDescription(
        key="device_ip",
        name="Device IP Address",
        value_path=("P", "IP"),
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


# --- Setup ------------------------------------------------------------------


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SolarwattConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Solarwatt sensors from a config entry."""
    coordinator: SolarwattDataUpdateCoordinator = entry.runtime_data

    async_add_entities(
        SolarwattSensor(
            coordinator,
            description,
            entry,
        )
        for description in SENSOR_ENTITIES
    )


# --- Entity -----------------------------------------------------------------


class SolarwattSensor(CoordinatorEntity[SolarwattDataUpdateCoordinator], SensorEntity):
    """Representation of a Solarwatt sensor."""

    entity_description: SolarwattSensorEntityDescription

    def __init__(
        self,
        coordinator: SolarwattDataUpdateCoordinator,
        description: SolarwattSensorEntityDescription,
        entry: SolarwattConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        # Description from our static SENSOR_ENTITIES table
        self.entity_description = description

        data: Any = coordinator.data or {}
        serial: str | None = None
        if isinstance(data, dict):
            serial = (data.get("ID") or {}).get("SN")

        self._serial = serial

        if serial:
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, serial)},
                name=f"SN: {serial}",
                manufacturer="Solarwatt",
                model="Battery Flex",
                serial_number=serial,
            )
            # unique_id based on serial + key
            assert entry.unique_id
            self._attr_unique_id = f"{serial}_{description.key}"
        else:
            self._attr_unique_id = description.key

    @property
    def name(self) -> str | None:
        """Return the name of the sensor prefixed with the device name."""
        base_name = super().name

        name_prefix: str | None = None
        if self._attr_device_info is not None:
            name_prefix = self._attr_device_info.get("name")

        if not name_prefix:
            name_prefix = "Solarwatt"

        if base_name:
            return f"{name_prefix} {base_name}"
        return name_prefix

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        data: Any = self.coordinator.data
        path = self.entity_description.value_path or ()

        for key in path:
            if not isinstance(data, dict):
                return None
            data = data.get(key)
            if data is None:
                return None

        if isinstance(data, (str, int, float)):
            return data

        return None

    @property
    def available(self) -> bool:
        """Return if the device is available."""
        current_serial: str | None = None
        data: Any = self.coordinator.data or {}
        if isinstance(data, dict):
            current_serial = (data.get("ID") or {}).get("SN")

        return super().available and self._serial == current_serial

    async def async_added_to_hass(self) -> None:
        """Run when entity is about to be added to Home Assistant."""
        await super().async_added_to_hass()

    async def async_will_remove_from_hass(self) -> None:
        """Run when entity will be removed from Home Assistant."""
        await super().async_will_remove_from_hass()
