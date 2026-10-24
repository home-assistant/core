"""Shared base entity for all WF-RAC platform entities."""

from typing import override

from homeassistant.core import callback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import WfRacCoordinator


class WfRacEntity(CoordinatorEntity[WfRacCoordinator]):
    """Base entity wired to the shared coordinator.

    Subclasses implement _update_state() and call it at the end of their own
    __init__.
    """

    def __init__(self, coordinator: WfRacCoordinator) -> None:
        """Wire the entity to the shared coordinator."""
        super().__init__(coordinator)
        self._attr_device_info = coordinator.device_info

    def _update_state(self) -> None:
        """Refresh entity state from the coordinator, overridden per platform."""
        raise NotImplementedError

    @override
    @callback
    def _handle_coordinator_update(self) -> None:
        self._update_state()
        self.async_write_ha_state()
