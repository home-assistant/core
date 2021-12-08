"""Sensors for Tesla Wall Connector."""
from dataclasses import dataclass
import logging

from homeassistant.components.sensor import (
    STATE_CLASS_MEASUREMENT,
    STATE_CLASS_TOTAL_INCREASING,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import (
    DEVICE_CLASS_ENERGY,
    DEVICE_CLASS_TEMPERATURE,
    DEVICE_CLASS_VOLTAGE,
    ELECTRIC_CURRENT_AMPERE,
    ELECTRIC_POTENTIAL_VOLT,
    ENERGY_WATT_HOUR,
    ENTITY_CATEGORY_DIAGNOSTIC,
    FREQUENCY_HERTZ,
    TEMP_CELSIUS,
)

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
        entity_category=ENTITY_CATEGORY_DIAGNOSTIC,
        value_fn=lambda data: data[WALLCONNECTOR_DATA_VITALS].evse_state,
    ),
    WallConnectorSensorDescription(
        key="handle_temp_c",
        name=prefix_entity_name("Handle Temperature"),
        native_unit_of_measurement=TEMP_CELSIUS,
        value_fn=lambda data: round(data[WALLCONNECTOR_DATA_VITALS].handle_temp_c, 1),
        device_class=DEVICE_CLASS_TEMPERATURE,
        entity_category=ENTITY_CATEGORY_DIAGNOSTIC,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    WallConnectorSensorDescription(
        key="grid_v",
        name=prefix_entity_name("Grid Voltage"),
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        value_fn=lambda data: round(data[WALLCONNECTOR_DATA_VITALS].grid_v, 1),
        device_class=DEVICE_CLASS_VOLTAGE,
        state_class=STATE_CLASS_MEASUREMENT,
        entity_category=ENTITY_CATEGORY_DIAGNOSTIC,
    ),
    WallConnectorSensorDescription(
        key="grid_hz",
        name=prefix_entity_name("Grid Frequency"),
        native_unit_of_measurement=FREQUENCY_HERTZ,
        value_fn=lambda data: round(data[WALLCONNECTOR_DATA_VITALS].grid_hz, 3),
        state_class=STATE_CLASS_MEASUREMENT,
        entity_category=ENTITY_CATEGORY_DIAGNOSTIC,
    ),
    WallConnectorSensorDescription(
        key="current_a_a",
        name=prefix_entity_name("Phase A Current"),
        native_unit_of_measurement=ELECTRIC_CURRENT_AMPERE,
        value_fn=lambda data: data[WALLCONNECTOR_DATA_VITALS].currentA_a,
        state_class=STATE_CLASS_MEASUREMENT,
        entity_category=ENTITY_CATEGORY_DIAGNOSTIC,
    ),
    WallConnectorSensorDescription(
        key="current_b_a",
        name=prefix_entity_name("Phase B Current"),
        native_unit_of_measurement=ELECTRIC_CURRENT_AMPERE,
        value_fn=lambda data: data[WALLCONNECTOR_DATA_VITALS].currentB_a,
        state_class=STATE_CLASS_MEASUREMENT,
        entity_category=ENTITY_CATEGORY_DIAGNOSTIC,
    ),
    WallConnectorSensorDescription(
        key="current_c_a",
        name=prefix_entity_name("Phase C Current"),
        native_unit_of_measurement=ELECTRIC_CURRENT_AMPERE,
        value_fn=lambda data: data[WALLCONNECTOR_DATA_VITALS].currentC_a,
        state_class=STATE_CLASS_MEASUREMENT,
        entity_category=ENTITY_CATEGORY_DIAGNOSTIC,
    ),
    WallConnectorSensorDescription(
        key="voltage_a_v",
        name=prefix_entity_name("Phase A Voltage"),
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        value_fn=lambda data: data[WALLCONNECTOR_DATA_VITALS].voltageA_v,
        state_class=STATE_CLASS_MEASUREMENT,
        entity_category=ENTITY_CATEGORY_DIAGNOSTIC,
    ),
    WallConnectorSensorDescription(
        key="voltage_b_v",
        name=prefix_entity_name("Phase B Voltage"),
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        value_fn=lambda data: data[WALLCONNECTOR_DATA_VITALS].voltageB_v,
        state_class=STATE_CLASS_MEASUREMENT,
        entity_category=ENTITY_CATEGORY_DIAGNOSTIC,
    ),
    WallConnectorSensorDescription(
        key="voltage_c_v",
        name=prefix_entity_name("Phase C Voltage"),
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        value_fn=lambda data: data[WALLCONNECTOR_DATA_VITALS].voltageC_v,
        state_class=STATE_CLASS_MEASUREMENT,
        entity_category=ENTITY_CATEGORY_DIAGNOSTIC,
    ),
    WallConnectorSensorDescription(
        key="energy_kWh",
        name=prefix_entity_name("Energy"),
        native_unit_of_measurement=ENERGY_WATT_HOUR,
        value_fn=lambda data: data[WALLCONNECTOR_DATA_LIFETIME].energy_wh,
        state_class=STATE_CLASS_TOTAL_INCREASING,
        device_class=DEVICE_CLASS_ENERGY,
    ),
]


async def async_setup_entry(hass, config_entry, async_add_devices):
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
