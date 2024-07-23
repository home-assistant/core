"""Sensors for Tesla Wall Connector."""

from dataclasses import dataclass
import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import (
    WallConnectorData,
    WallConnectorEntity,
    WallConnectorLambdaValueGetterMixin,
)
from .const import DOMAIN, WALLCONNECTOR_DATA_LIFETIME, WALLCONNECTOR_DATA_VITALS

_LOGGER = logging.getLogger(__name__)

EVSE_STATE = {
    0: "booting",
    1: "not_connected",
    2: "connected",
    4: "ready",
    6: "negotiating",
    7: "error",
    8: "charging_finished",
    9: "waiting_car",
    10: "charging_reduced",
    11: "charging",
}


@dataclass(frozen=True)
class WallConnectorSensorDescription(
    SensorEntityDescription, WallConnectorLambdaValueGetterMixin
):
    """Sensor entity description with a function pointer for getting sensor value."""


WALL_CONNECTOR_SENSORS = [
    WallConnectorSensorDescription(
        key="evse_state",
        translation_key="status_code",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data[WALLCONNECTOR_DATA_VITALS].evse_state,
        entity_registry_enabled_default=False,
    ),
    WallConnectorSensorDescription(
        key="status",
        translation_key="status",
        device_class=SensorDeviceClass.ENUM,
        value_fn=lambda data: EVSE_STATE.get(
            data[WALLCONNECTOR_DATA_VITALS].evse_state
        ),
        options=list(EVSE_STATE.values()),
    ),
    WallConnectorSensorDescription(
        key="handle_temp_c",
        translation_key="handle_temp_c",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda data: round(data[WALLCONNECTOR_DATA_VITALS].handle_temp_c, 1),
        device_class=SensorDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WallConnectorSensorDescription(
        key="grid_v",
        translation_key="grid_v",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        value_fn=lambda data: round(data[WALLCONNECTOR_DATA_VITALS].grid_v, 1),
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    WallConnectorSensorDescription(
        key="grid_hz",
        translation_key="grid_hz",
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        value_fn=lambda data: round(data[WALLCONNECTOR_DATA_VITALS].grid_hz, 3),
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    WallConnectorSensorDescription(
        key="current_a_a",
        translation_key="current_a_a",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        value_fn=lambda data: data[WALLCONNECTOR_DATA_VITALS].currentA_a,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    WallConnectorSensorDescription(
        key="current_b_a",
        translation_key="current_b_a",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        value_fn=lambda data: data[WALLCONNECTOR_DATA_VITALS].currentB_a,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    WallConnectorSensorDescription(
        key="current_c_a",
        translation_key="current_c_a",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        value_fn=lambda data: data[WALLCONNECTOR_DATA_VITALS].currentC_a,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    WallConnectorSensorDescription(
        key="voltage_a_v",
        translation_key="voltage_a_v",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        value_fn=lambda data: data[WALLCONNECTOR_DATA_VITALS].voltageA_v,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    WallConnectorSensorDescription(
        key="voltage_b_v",
        translation_key="voltage_b_v",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        value_fn=lambda data: data[WALLCONNECTOR_DATA_VITALS].voltageB_v,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    WallConnectorSensorDescription(
        key="voltage_c_v",
        translation_key="voltage_c_v",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        value_fn=lambda data: data[WALLCONNECTOR_DATA_VITALS].voltageC_v,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    WallConnectorSensorDescription(
        key="session_energy_wh",
        translation_key="session_energy_wh",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        value_fn=lambda data: data[WALLCONNECTOR_DATA_VITALS].session_energy_wh,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    WallConnectorSensorDescription(
        key="energy_kWh",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        value_fn=lambda data: data[WALLCONNECTOR_DATA_LIFETIME].energy_wh,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create the Wall Connector sensor devices."""
    wall_connector_data = hass.data[DOMAIN][config_entry.entry_id]

    all_entities = [
        WallConnectorSensorEntity(wall_connector_data, description)
        for description in WALL_CONNECTOR_SENSORS
    ]

    async_add_entities(all_entities)


class WallConnectorSensorEntity(WallConnectorEntity, SensorEntity):
    """Wall Connector Sensor Entity."""

    entity_description: WallConnectorSensorDescription

    def __init__(
        self,
        wall_connector_data: WallConnectorData,
        description: WallConnectorSensorDescription,
    ) -> None:
        """Initialize WallConnectorSensorEntity."""
        self.entity_description = description
        super().__init__(wall_connector_data)

    @property
    def native_value(self):
        """Return the state of the sensor."""

        return self.entity_description.value_fn(self.coordinator.data)
