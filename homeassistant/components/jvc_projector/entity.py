"""Base Entity for the jvc_projector integration."""

import logging

from jvcprojector import Command, JvcProjector

from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, NAME
from .coordinator import JvcProjectorDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


class JvcProjectorEntity(CoordinatorEntity[JvcProjectorDataUpdateCoordinator]):
    """Defines a base JVC Projector entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: JvcProjectorDataUpdateCoordinator,
        command: type[Command] | None = None,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator, command)

        self._attr_unique_id = coordinator.unique_id
        # The config entry unique id is the device's formatted MAC address (set
        # from the projector's MAC in the config flow), so it doubles as the
        # network MAC connection.
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._attr_unique_id)},
            connections={(CONNECTION_NETWORK_MAC, self._attr_unique_id)},
            name=NAME,
            model=self.device.model,
            manufacturer=MANUFACTURER,
        )

    @property
    def device(self) -> JvcProjector:
        """Return the device representing the projector."""
        return self.coordinator.device
