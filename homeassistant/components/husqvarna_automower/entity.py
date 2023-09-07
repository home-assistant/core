"""Platform for Husqvarna Automower base entity."""

import datetime
import logging
from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from . import AutomowerDataUpdateCoordinator
from .const import DOMAIN, HUSQVARNA_URL

_LOGGER = logging.getLogger(__name__)


class AutomowerEntity(CoordinatorEntity[AutomowerDataUpdateCoordinator]):
    """Defining the Automower base Entity."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, coordinator: AutomowerDataUpdateCoordinator, idx: int) -> None:
        """Initialize AutomowerEntity."""
        super().__init__(coordinator, context=idx)
        self.idx = idx
        self.mower = coordinator.session.data["data"][self.idx]
        self.mower_id = self.mower["id"]
        self.mower_name = self.mower_attributes["system"]["name"]
        self.model_name = self.mower_attributes["system"]["model"]

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self.mower_id)},
            name=self.mower_name,
            manufacturer="Husqvarna",
            model=self.model_name,
            configuration_url=HUSQVARNA_URL,
            suggested_area="Garden",
        )

    @property
    def mower_attributes(self) -> dict[str, Any]:
        """Get the mower attributes of the current mower."""
        return self.coordinator.session.data["data"][self.idx]["attributes"]

    def datetime_object(self, timestamp) -> datetime.datetime | None:
        """Convert the mower local timestamp to a UTC datetime object."""
        local: datetime.datetime | None
        if timestamp != 0:
            naive = datetime.datetime.fromtimestamp(timestamp / 1000, tz=None)
            local = dt_util.as_local(naive)
        if timestamp == 0:
            local = None
        return local

    async def async_added_to_hass(self) -> None:
        """Call when entity about to be added to Home Assistant."""
        await super().async_added_to_hass()
        self.coordinator.session.register_data_callback(
            lambda _: self.async_write_ha_state(), schedule_immediately=True
        )

    async def async_will_remove_from_hass(self) -> None:
        """Call when entity is being removed from Home Assistant."""
        await super().async_will_remove_from_hass()
        self.coordinator.session.unregister_data_callback(
            lambda _: self.async_write_ha_state()
        )
