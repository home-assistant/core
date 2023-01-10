"""Platform for sensor integration."""
from __future__ import annotations

from dataclasses import dataclass
import logging

from homeassistant import config_entries
from homeassistant.components import mqtt
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)

# from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    STATE_UNKNOWN,
    UnitOfElectricCurrent,
    UnitOfEnergy,
    UnitOfPower,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.json import json_loads

from . import ViarisEntityDescription
from .const import (  # REACTIVE_ENERGY_CONN2_KEY,; REACTIVE_POWER_CONN1_KEY,; REACTIVE_POWER_CONN2_KEY,; STATE_CONN2_KEY,; USER_CONN2_KEY,
    ACTIVE_ENERGY_CONN1_KEY,
    ACTIVE_ENERGY_CONN2_KEY,
    ACTIVE_POWER_CONN1_KEY,
    ACTIVE_POWER_CONN2_KEY,
    CONTAX_D0613_KEY,
    EVSE_POWER_KEY,
    HOME_POWER_KEY,
    OVERLOAD_REL_KEY,
    REACTIVE_ENERGY_CONN1_KEY,
    STATE_CONN1_KEY,
    TMC100_KEY,
    TOTAL_CURRENT_KEY,
    TOTAL_POWER_KEY,
    USER_CONN1_KEY,
)

# from homeassistant.helpers.typing import StateType
from .entity import ViarisEntity

# from typing import cast


_LOGGER = logging.getLogger(__name__)


@dataclass
class ViarisSensorEntityDescription(ViarisEntityDescription, SensorEntityDescription):
    """Describes Viaris sensor entity."""

    domain: str = "sensor"
    precision: int | None = None


def extract_state_conn1(value) -> int:
    """Extract state connector 1."""
    data = json_loads(value)
    return int(data["data"]["stat"]["state"])


def extract_item_from_array_to_float(value, key) -> float:
    """Extract item from array to float."""
    return float(json_loads(value)[int(key)])


def extract_item_from_array_to_int(value, key) -> int:
    """Extract item from array to int."""
    return int(json_loads(value)[int(key)])


def extract_item_from_array_to_bool(value, key) -> bool:
    """Extract item from array to int."""
    return bool(json_loads(value)[int(key)])


SENSOR_TYPES: tuple[ViarisSensorEntityDescription, ...] = (
    ViarisSensorEntityDescription(
        key=STATE_CONN1_KEY,
        icon="mdi:ev-plug-type2",
        name="Status",
    ),
    ViarisSensorEntityDescription(
        key=USER_CONN1_KEY,
        name="User",
        icon="mdi:account-card",
    ),
    ViarisSensorEntityDescription(
        key=STATE_CONN1_KEY,
        icon="mdi:power-socket-de",
        name="Status",
    ),
    ViarisSensorEntityDescription(
        key=USER_CONN1_KEY,
        name="User",
        icon="mdi:account-card",
    ),
    ViarisSensorEntityDescription(
        key=ACTIVE_ENERGY_CONN1_KEY,
        icon="mdi:lightning-bolt",
        name="Active Energy",
        precision=2,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    ViarisSensorEntityDescription(
        key=ACTIVE_ENERGY_CONN2_KEY,
        icon="mdi:lightning-bolt",
        name="Active Energy",
        precision=2,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    ViarisSensorEntityDescription(
        key=REACTIVE_ENERGY_CONN1_KEY,
        icon="mdi:lightning-bolt",
        name="Reactive Energy",
        precision=2,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    ViarisSensorEntityDescription(
        key=REACTIVE_ENERGY_CONN1_KEY,
        icon="mdi:lightning-bolt",
        name="Reactive Energy",
        precision=2,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    ViarisSensorEntityDescription(
        key=EVSE_POWER_KEY,
        icon="mdi:lightning-bolt",
        name="Evser Power",
        precision=2,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ViarisSensorEntityDescription(
        key=TOTAL_CURRENT_KEY,
        name="Total Current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    ViarisSensorEntityDescription(
        key=HOME_POWER_KEY,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ViarisSensorEntityDescription(
        key=TOTAL_POWER_KEY,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ViarisSensorEntityDescription(
        key=TMC100_KEY,
        icon="mdi:meter-electric",
    ),
    ViarisSensorEntityDescription(
        key=CONTAX_D0613_KEY,
        icon="mdi:meter-electric-outline",
    ),
    ViarisSensorEntityDescription(
        key=OVERLOAD_REL_KEY,
        icon="mdi:checkbox-blank-circle",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ViarisSensorEntityDescription(
        key=ACTIVE_POWER_CONN1_KEY,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ViarisSensorEntityDescription(
        key=ACTIVE_POWER_CONN2_KEY,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ViarisSensorEntityDescription(
        key=ACTIVE_POWER_CONN1_KEY,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ViarisSensorEntityDescription(
        key=ACTIVE_POWER_CONN2_KEY,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: config_entries.ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Viaris method."""
    async_add_entities(ViarisSensor(entry, description) for description in SENSOR_TYPES)


class ViarisSensor(ViarisEntity, SensorEntity):
    """Representation of the Viaris portal."""

    entity_description: ViarisSensorEntityDescription

    def __init__(
        self,
        config_entry: config_entries.ConfigEntry,
        description: ViarisSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(config_entry, description)

        self.entity_description = description

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._attr_native_value is not None

    async def async_added_to_hass(self) -> None:
        """Subscribe to MQTT events."""

        @callback
        def message_received(message):
            """Handle new MQTT messages."""
            if self.entity_description.state is not None:
                self._attr_native_value = self.entity_description.state(
                    message.payload, self.entity_description.attribute
                )
            else:
                if message.payload == "null":
                    self._attr_native_value = STATE_UNKNOWN
                else:
                    self._attr_native_value = message.payload

            self.async_write_ha_state()

        await mqtt.async_subscribe(self.hass, self._topic, message_received, 1)
