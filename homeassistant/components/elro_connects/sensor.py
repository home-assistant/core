"""The Elro Connects sensor platform."""
from __future__ import annotations

from dataclasses import dataclass
import logging

from elro.device import (
    ATTR_BATTERY_LEVEL,
    ATTR_DEVICE_STATE,
    ATTR_DEVICE_TYPE,
    ATTR_SIGNAL,
    STATES_OFFLINE,
)

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_NAME, PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.percentage import ranged_value_to_percentage

from .const import DOMAIN
from .device import ElroConnectsEntity, ElroConnectsK1

_LOGGER = logging.getLogger(__name__)


@dataclass
class ElroSensorDescription(SensorEntityDescription):
    """Class that holds senspr specific sensor info."""

    maximum_value: int | None = None


SENSOR_TYPES = {
    ATTR_BATTERY_LEVEL: ElroSensorDescription(
        key=ATTR_BATTERY_LEVEL,
        device_class="battery",
        state_class=SensorStateClass.MEASUREMENT,
        name="battery level",
        native_unit_of_measurement=PERCENTAGE,
        maximum_value=100,
    ),
    ATTR_SIGNAL: ElroSensorDescription(
        key=ATTR_SIGNAL,
        device_class="power_factor",
        state_class=SensorStateClass.MEASUREMENT,
        name="signal",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:signal",
        maximum_value=4,
        entity_registry_enabled_default=False,
    ),
    ATTR_DEVICE_STATE: ElroSensorDescription(
        key=ATTR_DEVICE_STATE,
        name="device state",
        icon="mdi:state-machine",
        maximum_value=None,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    elro_connects_api: ElroConnectsK1 = hass.data[DOMAIN][config_entry.entry_id]
    device_status: dict[int, dict] = elro_connects_api.coordinator.data

    async_add_entities(
        [
            ElroConnectsSensor(
                elro_connects_api,
                config_entry,
                device_id,
                SENSOR_TYPES[attribute],
            )
            for device_id, attributes in device_status.items()
            for attribute in attributes
            if attribute in SENSOR_TYPES
        ]
    )


class ElroConnectsSensor(ElroConnectsEntity, SensorEntity):
    """Elro Connects Fire Alarm Entity."""

    def __init__(
        self,
        elro_connects_api: ElroConnectsK1,
        entry: ConfigEntry,
        device_id: int,
        description: ElroSensorDescription,
    ) -> None:
        """Initialize a Fire Alarm Entity."""
        self._device_id = device_id
        self._elro_connects_api = elro_connects_api
        self.entity_description: ElroSensorDescription = description
        ElroConnectsEntity.__init__(
            self,
            elro_connects_api,
            entry,
            device_id,
            description,
        )

    @property
    def available(self) -> bool:
        """Return true if device is on or none if the device is offline."""
        return bool(self.data) and not (self.data[ATTR_DEVICE_STATE] in STATES_OFFLINE)

    @property
    def native_value(self) -> int | float | None:
        """Return the state of the sensor."""
        raw_value = self.data[self.entity_description.key]
        if max_value := self.entity_description.maximum_value:
            value = ranged_value_to_percentage((1, max_value), raw_value)
        else:
            value = raw_value
        return value if max_value is None or raw_value <= max_value else None

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return (
            f"{self.data[ATTR_NAME]} {self.entity_description.key}"
            if ATTR_NAME in self.data
            else f"{self.data[ATTR_DEVICE_TYPE]} {self.entity_description.key}"
        )
