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
    prefix_entity_name,
)
from .const import DOMAIN, WALLCONNECTOR_DATA_LIFETIME, WALLCONNECTOR_DATA_VITALS

_LOGGER = logging.getLogger(__name__)


@dataclass
class WallConnectorSensorDescription(
    SensorEntityDescription, WallConnectorLambdaValueGetterMixin
):
    """Sensor entity description with a function pointer for getting sensor value."""


WALL_CONNECTOR_SENSORS = [
    WallConnectorSensorDescription(
        key="evse_state",
        name=prefix_entity_name("State"),
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data[WALLCONNECTOR_DATA_VITALS].evse_state,
    ),
    WallConnectorSensorDescription(
        key="handle_temp_c",
        name=prefix_entity_name("Handle Temperature"),
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda data: round(data[WALLCONNECTOR_DATA_VITALS].handle_temp_c, 1),
        device_class=SensorDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WallConnectorSensorDescription(
        key="grid_v",
        name=prefix_entity_name("Grid Voltage"),
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        value_fn=lambda data: round(data[WALLCONNECTOR_DATA_VITALS].grid_v, 1),
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    WallConnectorSensorDescription(
        key="grid_hz",
        name=prefix_entity_name("Grid Frequency"),
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        value_fn=lambda data: round(data[WALLCONNECTOR_DATA_VITALS].grid_hz, 3),
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    WallConnectorSensorDescription(
        key="current_a_a",
        name=prefix_entity_name("Phase A Current"),
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        value_fn=lambda data: data[WALLCONNECTOR_DATA_VITALS].currentA_a,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    WallConnectorSensorDescription(
        key="current_b_a",
        name=prefix_entity_name("Phase B Current"),
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        value_fn=lambda data: data[WALLCONNECTOR_DATA_VITALS].currentB_a,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    WallConnectorSensorDescription(
        key="current_c_a",
        name=prefix_entity_name("Phase C Current"),
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        value_fn=lambda data: data[WALLCONNECTOR_DATA_VITALS].currentC_a,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    WallConnectorSensorDescription(
        key="voltage_a_v",
        name=prefix_entity_name("Phase A Voltage"),
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        value_fn=lambda data: data[WALLCONNECTOR_DATA_VITALS].voltageA_v,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    WallConnectorSensorDescription(
        key="voltage_b_v",
        name=prefix_entity_name("Phase B Voltage"),
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        value_fn=lambda data: data[WALLCONNECTOR_DATA_VITALS].voltageB_v,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    WallConnectorSensorDescription(
        key="voltage_c_v",
        name=prefix_entity_name("Phase C Voltage"),
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        value_fn=lambda data: data[WALLCONNECTOR_DATA_VITALS].voltageC_v,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    WallConnectorSensorDescription(
        key="energy_kWh",
        name=prefix_entity_name("Energy"),
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        value_fn=lambda data: data[WALLCONNECTOR_DATA_LIFETIME].energy_wh,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_devices: AddEntitiesCallback,
) -> None:
    """Create the Wall Connector sensor devices."""
    wall_connector_data = hass.data[DOMAIN][config_entry.entry_id]

    all_entities = [
        WallConnectorSensorEntity(wall_connector_data, description)
        for description in WALL_CONNECTOR_SENSORS
    ]

    async_add_devices(all_entities)


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
