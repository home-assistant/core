"""Home Connect entity base class."""

import logging

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from .api import HomeConnectDevice
from .const import DOMAIN, SIGNAL_UPDATE_ENTITIES

_LOGGER = logging.getLogger(__name__)


class HomeConnectEntity(Entity):
    """Generic Home Connect entity (base class)."""

    _attr_should_poll = False

    def __init__(self, device: HomeConnectDevice, desc: str) -> None:
        """Initialize the entity."""
        self.device = device
        self._attr_name = f"{device.appliance.name} {desc}"
        self._attr_unique_id = f"{device.appliance.haId}-{desc}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.appliance.haId)},
            manufacturer=device.appliance.brand,
            model=device.appliance.vib,
            name=device.appliance.name,
        )

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_UPDATE_ENTITIES, self._update_callback
            )
        )

    @callback
    def _update_callback(self, ha_id: str) -> None:
        """Update data."""
        if ha_id == self.device.appliance.haId:
            self.async_entity_update()

    @callback
    def async_entity_update(self) -> None:
        """Update the entity."""
        _LOGGER.debug("Entity update triggered on %s", self)
        self.async_schedule_update_ha_state(True)
