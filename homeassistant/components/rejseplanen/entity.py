"""Base entity for Rejseplanen integration."""

from __future__ import annotations

from dataclasses import dataclass
import logging

import homeassistant.helpers.device_registry as dr
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import RejseplanenDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class RejseplanenEntityContext:
    """Context for a Rejseplanen entity."""

    stop_id: int
    name: str
    subentry_id: str


class RejseplanenEntity(CoordinatorEntity[RejseplanenDataUpdateCoordinator]):
    """Base Rejseplanen entity."""

    _attr_has_entity_name = True
    _attr_attribution = "Data provided by rejseplanen.dk"

    def __init__(
        self,
        coordinator: RejseplanenDataUpdateCoordinator,
        context: RejseplanenEntityContext,
    ) -> None:
        """Initialize base entity."""
        super().__init__(coordinator, context=context)

        self._stop_id = context.stop_id

        # values so the device entry contains useful metadata for the stop.
        self._attr_device_info = dr.DeviceInfo(
            identifiers={(DOMAIN, context.subentry_id)},
            name=context.name,
            manufacturer="Rejseplanen",
        )
