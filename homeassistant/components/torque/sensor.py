

import logging
from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .torque_entity import TorqueEntity

from .const import (
    DOMAIN,
    SENSORS

)

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    """Setup the sensor platform."""

    coordinator = hass.data[DOMAIN][entry.entry_id]
    coordinator.async_add_entities = async_add_entities
    await coordinator.async_config_entry_first_refresh()

    sensor_list = []

    pid_to_load = await coordinator.store_available_sensors.async_load()
    for pid, [name, unit, icon] in SENSORS.items():
        if pid in pid_to_load:
            sensor =  TorqueSensor(hass, coordinator, coordinator.id, pid, name, unit, icon)
            sensor_list.append(sensor)

    async_add_entities(sensor_list, True)

    await coordinator.async_config_entry_first_refresh()



class TorqueSensor(TorqueEntity, SensorEntity, RestoreEntity):
    """Representation of a Torque sensor."""

    @property
    def state(self):
        """Return the state of the sensor."""

        return self._state

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self.coordinator.data:
            if self._pid in self.coordinator.data.keys():
                value = self.coordinator.data[self._pid]
                self._state = float("{:.3f}".format(value))
                self.async_write_ha_state()


    async def async_added_to_hass(self) -> None:
        """Call when entity about to be added to Home Assistant."""
        await super().async_added_to_hass()
        # __init__ will set self._state to self._initial, only override
        # if needed.
        state = await self.async_get_last_state()
        if state is not None:
            self._state = state.state
            return