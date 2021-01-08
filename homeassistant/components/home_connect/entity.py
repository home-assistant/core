"""Home Connect entity base class."""

import logging

from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from .api import HomeConnectDevice
from .const import DOMAIN, SIGNAL_UPDATE_ENTITIES

_LOGGER = logging.getLogger(__name__)


class HomeConnectEntity(Entity):
    """Generic Home Connect entity (base class)."""

    def __init__(self, device: HomeConnectDevice, desc: str) -> None:
        """Initialize the entity."""
        self.device = device
        self.desc = desc
        self._name = f"{self.device.appliance.name} {desc}"

    async def async_added_to_hass(self):
        """Register callbacks."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_UPDATE_ENTITIES, self._update_callback
            )
        )

    @callback
    def _update_callback(self, ha_id):
        """Update data."""
        if ha_id == self.device.appliance.haId:
            self.async_entity_update()

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def name(self):
        """Return the name of the node (used for Entity_ID)."""
        return self._name

    @property
    def unique_id(self):
        """Return the unique id base on the id returned by Home Connect and the entity name."""
        return f"{self.device.appliance.haId}-{self.desc}"

    @property
    def device_info(self):
        """Return info about the device."""
        return {
            "identifiers": {(DOMAIN, self.device.appliance.haId)},
            "name": self.device.appliance.name,
            "manufacturer": self.device.appliance.brand,
            "model": self.device.appliance.vib,
        }

    @callback
    def async_entity_update(self):
        """Update the entity."""
        _LOGGER.debug("Entity update triggered on %s", self)
        self.async_schedule_update_ha_state(True)
