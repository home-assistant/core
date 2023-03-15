"""Obihai Entity base class."""

from homeassistant.helpers.entity import Entity

from .connectivity import ObihaiConnection


class ObihaiEntity(Entity):
    """Obihai Entity base Class."""

    _attr_has_entity_name = True

    def __init__(self, requester: ObihaiConnection, service_name: str) -> None:
        """Initialize monitor sensor."""
        self._pyobihai = requester.pyobihai

        self._attr_unique_id = f"{requester.serial}-{service_name}"
        self._attr_name = service_name
        self._attr_device_info = requester.device_info
