"""Obihai Entity base class."""

from homeassistant.helpers.entity import Entity

from .connectivity import ObihaiConnection
from .const import OBIHAI


class ObihaiEntity(Entity):
    """Obihai Entity base Class."""

    _attr_has_entity_name = True

    def __init__(self, requester: ObihaiConnection, service_name: str) -> None:
        """Initialize monitor sensor."""

        self._pyobihai = requester.pyobihai
        self.requester = requester
        self._service_name = service_name

        self._attr_unique_id = f"{requester.serial}-{self._service_name}"
        self._attr_name = f"{OBIHAI} {self._service_name}"
