"""The base Packet of the LC7001 Engine."""

import json
import logging
from typing import Any

_LOGGER = logging.getLogger(__name__)


class Packet:
    """The base Packet of the LC7001 Engine."""

    def __init__(
        self, ID: int | None = None, Service: str | None = None, **kwargs
    ) -> None:
        """Initialize packet with ID and Service."""
        self.ID = ID
        self.Service = Service

    def setID(self, ID: int) -> None:
        """Set the ID of the packet."""
        self.ID = ID

    def asDict(self) -> dict[str, Any]:
        """Return a dict representation of packet."""
        selfDict: dict[str, Any] = {}

        if self.ID is not None:
            selfDict["ID"] = self.ID

        if self.Service is not None:
            selfDict["Service"] = self.Service

        return selfDict

    def toBytes(self) -> bytes:
        """Convert the packet to bytes."""
        return json.dumps(self.asDict()).encode()
