"""Sensor platform for Indevolt."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Final, cast

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfEnergy, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import DOMAIN
from .entity import IndevoltEntity


PARALLEL_UPDATES = 1

WORKING_MODE = {
    0: "Outdoor Portable",
    1: "Self-consumed Prioritized",
    5: "Charge/Discharge Schedule",
}

BATTERY_CHARGE_DISCHARGE_STATE = {1000: "Static", 1001: "Charging", 1002: "Discharging"}

METER_CONNECTION_STATUS = {1000: "ON", 1001: "OFF"}


@dataclass(frozen=True, kw_only=True)
class IndevoltSensorEntityDescription(SensorEntityDescription):
    """Class to describe a sensor entity."""

    value_fn: Callable[[dict[str, str]], StateType]
    translation_key: str
    entity_category: EntityCategory | None = None


SENSORS: Final = (
    IndevoltSensorEntityDescription(
        key="1664",
        translation_key="dc_input_power1",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: cast(float, data["1664"]),
    ),
    IndevoltSensorEntityDescription(
        key="1665",
        translation_key="dc_input_power2",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: cast(float, data["1665"]),
    ),
    IndevoltSensorEntityDescription(
        key="2108",
        translation_key="total_ac_output_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: cast(float, data["2108"]),
    ),
    IndevoltSensorEntityDescription(
        key="1502",
        translation_key="daily_production",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: cast(float, data["1502"]),
    ),
    IndevoltSensorEntityDescription(
        key="1505",
        translation_key="cumulative_production",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: cast(float, data["1505"]) * 0.001,
    ),
    IndevoltSensorEntityDescription(
        key="2101",
        translation_key="total_ac_input_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: cast(float, data["2101"]),
    ),
    IndevoltSensorEntityDescription(
        key="2107",
        translation_key="total_ac_input_energy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: cast(float, data["2107"]),
    ),
    IndevoltSensorEntityDescription(
        key="1501",
        translation_key="total_dc_output_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: cast(float, data["1501"]),
    ),
    IndevoltSensorEntityDescription(
        key="6000",
        translation_key="battery_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: cast(float, data["6000"]),
    ),
    IndevoltSensorEntityDescription(
        key="6002",
        translation_key="battery_soc",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: cast(float, data["6002"]),
    ),
    IndevoltSensorEntityDescription(
        key="6105",
        translation_key="emergency_power_supply",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: cast(float, data["6105"]),
    ),
    IndevoltSensorEntityDescription(
        key="6004",
        translation_key="battery_daily_charging_energy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: cast(float, data["6004"]),
    ),
    IndevoltSensorEntityDescription(
        key="6005",
        translation_key="battery_daily_discharging_energy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: cast(float, data["6005"]),
    ),
    IndevoltSensorEntityDescription(
        key="6006",
        translation_key="battery_total_charging_energy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: cast(float, data["6006"]),
    ),
    IndevoltSensorEntityDescription(
        key="6007",
        translation_key="battery_total_discharging_energy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: cast(float, data["6007"]),
    ),
    IndevoltSensorEntityDescription(
        key="21028",
        translation_key="meter_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: cast(float, data["21028"]),
    ),
    IndevoltSensorEntityDescription(
        key="7101",
        translation_key="working_mode",
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        options=list(WORKING_MODE.values()),
        value_fn=lambda data: WORKING_MODE.get(cast(int, data["7101"])),
    ),
    IndevoltSensorEntityDescription(
        key="6001",
        translation_key="battery_charge_discharge_state",
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        options=list(BATTERY_CHARGE_DISCHARGE_STATE.values()),
        value_fn=lambda data: BATTERY_CHARGE_DISCHARGE_STATE.get(
            cast(int, data["6001"])
        ),
    ),
    IndevoltSensorEntityDescription(
        key="7120",
        translation_key="meter_connection_status",
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        options=list(METER_CONNECTION_STATUS.values()),
        value_fn=lambda data: METER_CONNECTION_STATUS.get(cast(int, data["7120"])),
    ),
    IndevoltSensorEntityDescription(
        key="1666",
        translation_key="dc_input_power3",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: cast(float, data["1666"]),
    ),
    IndevoltSensorEntityDescription(
        key="1667",
        translation_key="dc_input_power4",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: cast(float, data["1667"]),
    ),
    IndevoltSensorEntityDescription(
        key="142",
        translation_key="rated_capacity",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: cast(float, data["142"]),
    ),
    IndevoltSensorEntityDescription(
        key="6009",
        translation_key="battery_soc",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: cast(float, data["6009"]),
    ),
    IndevoltSensorEntityDescription(
        key="11016",
        translation_key="meter_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: cast(float, data["11016"]),
    ),
    IndevoltSensorEntityDescription(
        key="667",
        translation_key="bypass_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: cast(float, data["667"]),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up sensors from a config entry."""
    entities = [
        IndevoltSensorEntity(entry.runtime_data, description)
        for description in SENSORS
        if entry.runtime_data.data.get(description.key) is not None
    ]

    async_add_entities(entities)


class IndevoltSensorEntity(IndevoltEntity, SensorEntity):
    """Representation of a Indevolt sensor."""

    entity_description: IndevoltSensorEntityDescription

    def __init__(
        self, coordinator, description: IndevoltSensorEntityDescription
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = (
            f"{DOMAIN}_{coordinator.config_entry.unique_id}_{description.key}"
        )

    @property
    def native_value(self) -> StateType:
        """Return value of sensor."""
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def available(self) -> bool:
        """Return availability of sensor."""
        return super().available and self.native_value is not None
