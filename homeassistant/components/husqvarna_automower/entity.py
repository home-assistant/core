"""Platform for Husqvarna Automower base entity."""

import logging

from aioautomower.session import MowerAttributes

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import AutomowerDataUpdateCoordinator
from .const import DOMAIN, HUSQVARNA_URL

_LOGGER = logging.getLogger(__name__)


class AutomowerEntity(CoordinatorEntity[AutomowerDataUpdateCoordinator]):
    """Defining the Automower base Entity."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, coordinator: AutomowerDataUpdateCoordinator, idx: int) -> None:
        """Initialize AutomowerEntity."""
        super().__init__(coordinator, idx)
        self.idx = idx
        self.mower_id = coordinator.session.dataclass.data[idx].id
        mower_name = self.mower_attributes.system.name
        mower_model = self.mower_attributes.system.model

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self.mower_id)},
            name=mower_name,
            manufacturer="Husqvarna",
            model=mower_model,
            configuration_url=HUSQVARNA_URL,
            suggested_area="Garden",
        )

    @property
    def mower_attributes(self) -> MowerAttributes:
        """Get the mower attributes of the current mower."""
        return self.coordinator.session.dataclass.data[self.idx].attributes

    async def async_added_to_hass(self) -> None:
        """Call when entity about to be added to Home Assistant."""
        await super().async_added_to_hass()
        self.coordinator.session.register_data_callback(
            self.callback, schedule_immediately=True
        )

    async def async_will_remove_from_hass(self) -> None:
        """Call when entity is being removed from Home Assistant."""
        await super().async_will_remove_from_hass()
        self.coordinator.session.unregister_data_callback(self.callback)

    @callback
    def callback(self, _):
        """Is called on an update of the library and writes new state to the entity."""
        self.async_write_ha_state()
