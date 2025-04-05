"""The base Packet of the LC7001 Engine."""

import json
import logging
from typing import Any

from .json import Jsonable

_LOGGER = logging.getLogger(__name__)


class Packet(Jsonable):
    """The base Packet of the LC7001 Engine."""

    _service_name: str | None = None

    def __init__(
        self, ID: int | None = None, Service: str | None = _service_name, **kwargs: Any
    ) -> None:
        """Initialize packet with ID and Service."""
        self.ID = ID
        self.Service = Service or self._service_name

    def setID(self, ID: int) -> None:
        """Set the ID of the packet."""
        self.ID = ID

    def toBytes(self) -> bytes:
        """Convert the packet to bytes."""
        return json.dumps(self.asDict()).encode()
