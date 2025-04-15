"""Support for the Nissan Leaf Carwings/Nissan Connect API."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from . import LeafDataStore
from .const import SIGNAL_UPDATE_LEAF

_LOGGER = logging.getLogger(__name__)


class LeafEntity(Entity):
    """Base class for Nissan Leaf entity."""

    def __init__(self, car: LeafDataStore) -> None:
        """Store LeafDataStore upon init."""
        self.car = car

    def log_registration(self) -> None:
        """Log registration."""
        _LOGGER.debug(
            "Registered %s integration for VIN %s",
            self.__class__.__name__,
            self.car.leaf.vin,
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return default attributes for Nissan leaf entities."""
        return {
            "next_update": self.car.next_update,
            "last_attempt": self.car.last_check,
            "updated_on": self.car.last_battery_response,
            "update_in_progress": self.car.request_in_progress,
            "vin": self.car.leaf.vin,
        }

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        self.log_registration()
        self.async_on_remove(
            async_dispatcher_connect(
                self.car.hass, SIGNAL_UPDATE_LEAF, self._update_callback
            )
        )

    @callback
    def _update_callback(self) -> None:
        """Update the state."""
        self.async_schedule_update_ha_state(True)
