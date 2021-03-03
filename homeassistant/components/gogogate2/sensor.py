"""Support for Gogogate2 garage Doors."""
from typing import Callable, List, Optional

from gogogate2_api.common import get_configured_doors

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import DEVICE_CLASS_BATTERY
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity

from .common import GoGoGate2Entity, get_data_update_coordinator

SENSOR_ID_WIRED = "WIRE"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: Callable[[List[Entity], Optional[bool]], None],
) -> None:
    """Set up the config entry."""
    data_update_coordinator = get_data_update_coordinator(hass, config_entry)

    async_add_entities(
        [
            DoorSensor(config_entry, data_update_coordinator, door)
            for door in get_configured_doors(data_update_coordinator.data)
            if door.sensorid and door.sensorid != SENSOR_ID_WIRED
        ]
    )


class DoorSensor(GoGoGate2Entity):
    """Sensor entity for goggate2."""

    @property
    def name(self):
        """Return the name of the door."""
        return f"{self._get_door().name} battery"

    @property
    def device_class(self):
        """Return the class of this device, from component DEVICE_CLASSES."""
        return DEVICE_CLASS_BATTERY

    @property
    def state(self):
        """Return the state of the entity."""
        door = self._get_door()
        return door.voltage  # This is a percentage, not an absolute voltage

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        door = self._get_door()
        if door.sensorid is not None:
            return {"door_id": door.door_id, "sensor_id": door.sensorid}
        return None
