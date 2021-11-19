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
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_TEMPERATURE,
    DEVICE_CLASS_VOLTAGE,
    ELECTRIC_POTENTIAL_VOLT,
    ENERGY_KILO_WATT_HOUR,
    ENTITY_CATEGORY_DIAGNOSTIC,
    FREQUENCY_HERTZ,
    POWER_KILO_WATT,
    TEMP_CELSIUS,
)

from . import (
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


wall_connector_sensors = [
    WallConnectorSensorDescription(
        key="evse_state",
        name=prefix_entity_name("State"),
        entity_category=ENTITY_CATEGORY_DIAGNOSTIC,
        value_getter=lambda data: data[WALLCONNECTOR_DATA_VITALS].evse_state,
    ),
    WallConnectorSensorDescription(
        key="handle_temp_c",
        name=prefix_entity_name("Handle Temperature"),
        native_unit_of_measurement=TEMP_CELSIUS,
        value_getter=lambda data: data[WALLCONNECTOR_DATA_VITALS].handle_temp_c,
        device_class=DEVICE_CLASS_TEMPERATURE,
        entity_category=ENTITY_CATEGORY_DIAGNOSTIC,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    WallConnectorSensorDescription(
        key="grid_v",
        name=prefix_entity_name("Grid Voltage"),
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        value_getter=lambda data: data[WALLCONNECTOR_DATA_VITALS].grid_v,
        device_class=DEVICE_CLASS_VOLTAGE,
        state_class=STATE_CLASS_MEASUREMENT,
        entity_category=ENTITY_CATEGORY_DIAGNOSTIC,
    ),
    WallConnectorSensorDescription(
        key="grid_hz",
        name=prefix_entity_name("Grid Frequency"),
        native_unit_of_measurement=FREQUENCY_HERTZ,
        value_getter=lambda data: data[WALLCONNECTOR_DATA_VITALS].grid_hz,
        state_class=STATE_CLASS_MEASUREMENT,
        entity_category=ENTITY_CATEGORY_DIAGNOSTIC,
    ),
    WallConnectorSensorDescription(
        key="power",
        name=prefix_entity_name("Power"),
        native_unit_of_measurement=POWER_KILO_WATT,
        value_getter=lambda data: round(
            (
                (
                    data[WALLCONNECTOR_DATA_VITALS].currentA_a
                    * data[WALLCONNECTOR_DATA_VITALS].voltageA_v
                )
                + (
                    data[WALLCONNECTOR_DATA_VITALS].currentB_a
                    * data[WALLCONNECTOR_DATA_VITALS].voltageB_v
                )
                + (
                    data[WALLCONNECTOR_DATA_VITALS].currentC_a
                    * data[WALLCONNECTOR_DATA_VITALS].voltageC_v
                )
            )
            / 1000.0,
            1,
        ),
        device_class=DEVICE_CLASS_POWER,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    WallConnectorSensorDescription(
        key="total_energy_kWh",
        name=prefix_entity_name("Total Energy"),
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        value_getter=lambda data: data[WALLCONNECTOR_DATA_LIFETIME].energy_wh / 1000.0,
        state_class=STATE_CLASS_TOTAL_INCREASING,
        device_class=DEVICE_CLASS_ENERGY,
    ),
]


async def async_setup_entry(hass, config_entry, async_add_devices):
    """Create the Wall Connector sensor devices."""
    wall_connector = hass.data[DOMAIN][config_entry.entry_id]

    all_entities = []
    for description in wall_connector_sensors:
        entity = WallConnectorSensorEntity(wall_connector, description)
        if entity is not None:
            all_entities.append(entity)

    async_add_devices(all_entities)


class WallConnectorSensorEntity(WallConnectorEntity, SensorEntity):
    """Wall Connector Sensor Entity."""

    entity_description: WallConnectorSensorDescription

    def __init__(
        self, wall_connector: dict, description: WallConnectorSensorDescription
    ) -> None:
        """Initialize WallConnectorSensorEntity."""
        self.entity_description = description
        super().__init__(wall_connector)

    @property
    def state(self):
        """Return the state of the sensor."""
        if self.coordinator.data is None:
            return None

        return self.entity_description.value_getter(self.coordinator.data)
