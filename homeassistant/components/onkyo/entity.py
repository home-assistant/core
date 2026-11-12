"""Base entity for Onkyo."""

from typing import override

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN
from .receiver import ReceiverManager


class OnkyoEntity(Entity):
    """Base class for Onkyo entities."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, manager: ReceiverManager) -> None:
        """Initialize the entity."""
        self._manager = manager
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, manager.info.identifier)}
        )

    @property
    @override
    def available(self) -> bool:
        """Return if entity is available."""
        return self._manager.connected
